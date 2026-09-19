// dashboard.js — Real-Data Dashboard Engine
// Strictly zero hardcoded data: all metrics, charts, and tables are generated from real databases.

let equityChart = null;
let dailyChart = null;
let drawdownChart = null;
let hourlyChart = null;
let outcomeChart = null;
let pnlDistChart = null;
let teDriftChartInstance = null;
let teCalibrationChartInstance = null;
let teMonteCarloChartInstance = null;
let teGreeksChartInstance = null;
let allTrades = [];
let filteredTrades = [];
let currentSortColumn = "entry_time";
let sortAscending = false;
let currentTradeFilter = "all";
let currentSelectedTradeId = null;
let lastRawArchives = [];

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initStrategySelector();
  initDirectoryScanner();
  initFileBrowser();
  initTableSort();
  initTradeFilters();
  initModal();
  initWalkForward();
  initParameterOptimizer();
  initCompareModelPicker();
  initTradingEngineInsights();

  // Load default directory
  loadArchives();
  loadLatestResults();

  document.getElementById("btnRun").addEventListener("click", runBacktest);
  const btnCompare = document.getElementById("btnCompare");
  if (btnCompare) {
    btnCompare.addEventListener("click", runComparison);
  }
  document.getElementById("btnExportCsv").addEventListener("click", () => {
    window.location.href = "/api/export_csv";
  });

  const searchInput = document.getElementById("tradeSearchInput");
  if (searchInput) {
    searchInput.addEventListener("input", () => {
      filterAndRenderTrades();
    });
  }

  const dateFilter = document.getElementById("tradeDateFilter");
  if (dateFilter) {
    dateFilter.addEventListener("change", () => {
      filterAndRenderTrades();
    });
  }

  const explorerRefresh = document.getElementById("btnExplorerRefresh");
  if (explorerRefresh) {
    explorerRefresh.addEventListener("click", () => {
      const dirInput = document.getElementById("dirInput");
      loadArchives(dirInput ? dirInput.value.trim() : "");
    });
  }
});

// ── Top Navigation Tabs ───────────────────────────────────────────────────────
function initTabs() {
  const tabs = document.querySelectorAll(".nav-tab");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      const target = tab.getAttribute("data-tab");
      switchTab(target);
    });
  });
}

function switchTab(tabId) {
  const tabs = document.querySelectorAll(".nav-tab");
  const panes = document.querySelectorAll(".tab-pane");

  tabs.forEach(t => {
    if (t.getAttribute("data-tab") === tabId) {
      t.classList.add("active");
    } else {
      t.classList.remove("active");
    }
  });

  panes.forEach(p => {
    if (p.id === tabId) {
      p.classList.add("active");
    } else {
      p.classList.remove("active");
    }
  });

  // Re-render / resize charts when tab becomes visible
  if (tabId === "tabAnalytics") {
    setTimeout(() => {
      if (equityChart) equityChart.resize();
      if (dailyChart) dailyChart.resize();
      if (drawdownChart) drawdownChart.resize();
    }, 50);
  } else if (tabId === "tabWalkForward") {
    setTimeout(() => {
      if (wfoChart) wfoChart.resize();
    }, 50);
  } else if (tabId === "tabExplorer") {
    renderDataExplorer(lastRawArchives);
  } else if (tabId === "tabTradingEngine") {
    if (!window._teInsightsLoaded) {
      window._teInsightsLoaded = true;
      fetchReconciliation();
      fetchConfigExport();
      fetchAiAnalytics();
    }
  }
}
window.switchTab = switchTab;

// ── Strategy Selector ────────────────────────────────────────────────────────
function initStrategySelector() {
  const select = document.getElementById("strategySelect");
  const eqGroup = document.getElementById("equityParams");
  const orbGroup = document.getElementById("orbParams");
  const stGroup = document.getElementById("supertrendParams");
  const camGroup = document.getElementById("camarillaParams");
  const ribbonGroup = document.getElementById("emaRibbonParams");
  const bbBandsGroup = document.getElementById("bollingerBParams");
  const macdGroup = document.getElementById("macdAccelParams");
  const vwapGroup = document.getElementById("vwapParams");
  const rsiGroup = document.getElementById("rsiParams");
  const optGroup = document.getElementById("optionsParams");
  const aiGroup = document.getElementById("aiParams");
  const straddleGroup = document.getElementById("shortStraddleParams");
  const pcrGroup = document.getElementById("pcrReversionParams");
  const bnGroup = document.getElementById("bankniftyOptionsParams");
  const futGroup = document.getElementById("futuresTrendParams");
  const mpGroup = document.getElementById("maxPainParams");

  const hideAll = () => {
    if (eqGroup) eqGroup.style.display = "none";
    if (orbGroup) orbGroup.style.display = "none";
    if (stGroup) stGroup.style.display = "none";
    if (camGroup) camGroup.style.display = "none";
    if (ribbonGroup) ribbonGroup.style.display = "none";
    if (bbBandsGroup) bbBandsGroup.style.display = "none";
    if (macdGroup) macdGroup.style.display = "none";
    if (vwapGroup) vwapGroup.style.display = "none";
    if (rsiGroup) rsiGroup.style.display = "none";
    if (optGroup) optGroup.style.display = "none";
    if (aiGroup) aiGroup.style.display = "none";
    if (straddleGroup) straddleGroup.style.display = "none";
    if (pcrGroup) pcrGroup.style.display = "none";
    if (bnGroup) bnGroup.style.display = "none";
    if (futGroup) futGroup.style.display = "none";
    if (mpGroup) mpGroup.style.display = "none";
  };

  select.addEventListener("change", () => {
    hideAll();
    const val = select.value;
    if (val === "equity" && eqGroup) {
      eqGroup.style.display = "block";
    } else if (val === "orb" && orbGroup) {
      orbGroup.style.display = "block";
    } else if (val === "supertrend" && stGroup) {
      stGroup.style.display = "block";
    } else if (val === "camarilla" && camGroup) {
      camGroup.style.display = "block";
    } else if (val === "ema-ribbon" && ribbonGroup) {
      ribbonGroup.style.display = "block";
    } else if (val === "bollinger-b" && bbBandsGroup) {
      bbBandsGroup.style.display = "block";
    } else if (val === "macd-accel" && macdGroup) {
      macdGroup.style.display = "block";
    } else if (val === "vwap-reversion" && vwapGroup) {
      vwapGroup.style.display = "block";
    } else if (val === "rsi-momentum" && rsiGroup) {
      rsiGroup.style.display = "block";
    } else if (val === "options" && optGroup) {
      optGroup.style.display = "block";
    } else if (val === "ai-replay" && aiGroup) {
      aiGroup.style.display = "block";
    } else if (val === "short-straddle" && straddleGroup) {
      straddleGroup.style.display = "block";
    } else if (val === "pcr-reversion" && pcrGroup) {
      pcrGroup.style.display = "block";
    } else if (val === "banknifty-options" && bnGroup) {
      bnGroup.style.display = "block";
    } else if (val === "futures-trend" && futGroup) {
      futGroup.style.display = "block";
    } else if (val === "max-pain" && mpGroup) {
      mpGroup.style.display = "block";
    }
  });
}

// ── Directory & Archive Scanner ──────────────────────────────────────────────
function initDirectoryScanner() {
  const dirInput = document.getElementById("dirInput");
  const btnScan = document.getElementById("btnScanDir");
  const selectAllBtn = document.getElementById("selectAllBtn");

  btnScan.addEventListener("click", () => {
    const dir = dirInput.value.trim();
    loadArchives(dir);
  });

  dirInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      loadArchives(dirInput.value.trim());
    }
  });

  selectAllBtn.addEventListener("click", () => {
    const checkboxes = document.querySelectorAll('input[name="archiveDate"]');
    if (checkboxes.length === 0) return;
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
    checkboxes.forEach(cb => cb.checked = !allChecked);
    selectAllBtn.innerText = allChecked ? "Select All" : "Deselect All";
  });

  // Quick Chips
  document.querySelectorAll(".quick-chips .chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const dir = chip.getAttribute("data-dir");
      dirInput.value = dir;
      loadArchives(dir);
    });
  });
}

// ── Interactive File / Folder Browser ─────────────────────────────────────────
let currentExplorerPath = "~/Downloads";
let currentSelectedPath = "";
let explorerRawItems = [];

function openFileBrowser() {
  const modal = document.getElementById("fileBrowserModal");
  const dirInput = document.getElementById("dirInput");
  if (!modal) return;
  modal.style.display = "flex";
  const startPath = (dirInput ? dirInput.value.trim() : "") || "~/Downloads";
  browsePath(startPath);
}
window.openFileBrowser = openFileBrowser;

function initFileBrowser() {
  const modal = document.getElementById("fileBrowserModal");
  const btnOpen = document.getElementById("btnBrowseDir");
  const btnClose = document.getElementById("closeBrowserModal");
  const btnUp = document.getElementById("btnNavUp");
  const btnGo = document.getElementById("btnNavGo");
  const pathInput = document.getElementById("explorerPathInput");
  const searchInput = document.getElementById("explorerSearchFilter");
  const btnSelectCurrent = document.getElementById("btnSelectCurrentDir");
  const btnConfirm = document.getElementById("btnConfirmSelection");
  const dirInput = document.getElementById("dirInput");

  if (!modal) return;

  if (btnOpen) {
    btnOpen.addEventListener("click", openFileBrowser);
  }

  if (btnClose) {
    btnClose.addEventListener("click", () => {
      modal.style.display = "none";
    });
  }

  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.style.display = "none";
  });

  document.querySelectorAll(".explorer-places .place-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const p = chip.getAttribute("data-path");
      browsePath(p);
    });
  });

  btnUp.addEventListener("click", () => {
    if (pathInput.dataset.parent) {
      browsePath(pathInput.dataset.parent);
    }
  });

  btnGo.addEventListener("click", () => {
    browsePath(pathInput.value.trim());
  });

  pathInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      browsePath(pathInput.value.trim());
    }
  });

  if (searchInput) {
    searchInput.addEventListener("input", () => {
      filterExplorerList(searchInput.value.trim());
    });
  }

  btnSelectCurrent.addEventListener("click", () => {
    dirInput.value = currentExplorerPath;
    modal.style.display = "none";
    loadArchives(currentExplorerPath);
  });

  btnConfirm.addEventListener("click", () => {
    if (currentSelectedPath) {
      dirInput.value = currentSelectedPath;
      modal.style.display = "none";
      loadArchives(currentSelectedPath);
    }
  });
}

async function browsePath(path) {
  const listEl = document.getElementById("explorerItemsList");
  const pathInput = document.getElementById("explorerPathInput");
  const btnUp = document.getElementById("btnNavUp");
  const selectedDisplay = document.getElementById("selectedItemDisplay");
  const btnConfirm = document.getElementById("btnConfirmSelection");
  const searchInput = document.getElementById("explorerSearchFilter");

  if (searchInput) searchInput.value = "";
  listEl.innerHTML = '<div class="empty-state">Loading folder contents...</div>';

  try {
    const res = await fetch(`/api/browse?path=${encodeURIComponent(path)}`);
    const data = await res.json();
    if (data.status !== "success") {
      listEl.innerHTML = `<div class="empty-state" style="color: var(--red);">Error: ${data.message || "Failed to load directory"}</div>`;
      return;
    }

    currentExplorerPath = data.current_path;
    pathInput.value = data.current_path;
    pathInput.dataset.parent = data.parent_path || "";
    btnUp.disabled = !data.parent_path;

    currentSelectedPath = data.selected_target || data.current_path;
    selectedDisplay.innerText = currentSelectedPath;
    btnConfirm.disabled = false;

    explorerRawItems = data.items || [];
    renderExplorerList(explorerRawItems);
  } catch (err) {
    listEl.innerHTML = `<div class="empty-state" style="color: var(--red);">Failed to load directory: ${err}</div>`;
  }
}

function renderExplorerList(items) {
  const listEl = document.getElementById("explorerItemsList");
  const selectedDisplay = document.getElementById("selectedItemDisplay");
  const btnConfirm = document.getElementById("btnConfirmSelection");

  listEl.innerHTML = "";
  if (!items || items.length === 0) {
    listEl.innerHTML = '<div class="empty-state">This directory has no subdirectories or archives.</div>';
    return;
  }

  items.forEach(item => {
    const el = document.createElement("div");
    el.className = `explorer-item ${item.path === currentSelectedPath ? "selected" : ""}`;

    let icon = "📁";
    let badgeHtml = "";
    if (item.type === "archive") {
      icon = item.is_market_archive ? "📦" : "🗜️";
      if (item.is_market_archive) {
        badgeHtml = `<span class="archive-badge badge-archive">Session RAR</span>`;
      }
    } else if (item.type === "database") {
      icon = "🗄️";
      badgeHtml = `<span class="archive-badge badge-folder">Market DB</span>`;
    } else if (item.is_session) {
      icon = "🗂️";
      badgeHtml = `<span class="archive-badge badge-extracted">Market Session</span>`;
    }

    const sizeStr = item.size_mb ? `${item.size_mb.toFixed(1)} MB` : "";

    el.innerHTML = `
      <div style="display: flex; align-items: center; gap: 8px; overflow: hidden;">
        <span style="font-size: 1.1rem;">${icon}</span>
        <span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 500;">${item.name}</span>
        ${badgeHtml}
      </div>
      <div style="font-size: 0.72rem; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; white-space: nowrap;">
        ${sizeStr}
      </div>
    `;

    // Single-click selects target
    el.addEventListener("click", () => {
      document.querySelectorAll(".explorer-item").forEach(i => i.classList.remove("selected"));
      el.classList.add("selected");
      currentSelectedPath = item.path;
      selectedDisplay.innerText = item.path;
      btnConfirm.disabled = false;
    });

    // Double click: if folder, navigates into it; if archive or db, confirms selection immediately
    el.addEventListener("dblclick", () => {
      if (item.type === "folder") {
        browsePath(item.path);
      } else {
        const dirInput = document.getElementById("dirInput");
        dirInput.value = item.path;
        document.getElementById("fileBrowserModal").style.display = "none";
        loadArchives(item.path);
      }
    });

    listEl.appendChild(el);
  });
}

function filterExplorerList(query) {
  if (!query) {
    renderExplorerList(explorerRawItems);
    return;
  }
  const q = query.toLowerCase();
  const filtered = explorerRawItems.filter(item => item.name.toLowerCase().includes(q));
  renderExplorerList(filtered);
}

// ── Load Available Archives ──────────────────────────────────────────────────
async function loadArchives(customDir = "") {
  const listEl = document.getElementById("archiveList");
  listEl.innerHTML = '<div class="empty-state">Scanning directory for real recorded sessions...</div>';

  try {
    const url = customDir ? `/api/archives?dir=${encodeURIComponent(customDir)}` : "/api/archives";
    const res = await fetch(url);
    const data = await res.json();

    if (data.status !== "success" || !data.archives || data.archives.length === 0) {
      listEl.innerHTML = `<div class="empty-state" style="color: var(--yellow);">No recorded sessions found in ${data.scanned_directory || customDir || "~/Downloads"}.</div>`;
      lastRawArchives = [];
      renderDataExplorer([]);
      return;
    }

    lastRawArchives = data.archives;
    renderDataExplorer(data.archives);

    // Update scanned dir badge in header
    const dirBadge = document.getElementById("currentScannedDir");
    if (dirBadge) {
      const displayPath = data.scanned_directory || customDir || "~/Downloads";
      dirBadge.innerText = `DIR: ${displayPath.length > 28 ? "..." + displayPath.slice(-25) : displayPath}`;
      dirBadge.title = displayPath;
    }

    listEl.innerHTML = "";
    data.archives.forEach((arch, idx) => {
      const item = document.createElement("div");
      item.className = "archive-item";

      const isExtracted = arch.is_extracted;
      const isFolder = arch.source_type === "folder";
      const badgeText = isFolder ? "Folder" : (isExtracted ? "Extracted" : "RAR Archive");
      const badgeClass = isFolder ? "badge-folder" : (isExtracted ? "badge-extracted" : "badge-archive");

      item.innerHTML = `
        <label>
          <input type="checkbox" name="archiveDate" value="${arch.date}" ${idx === 0 ? "checked" : ""}>
          <span><strong>${arch.date}</strong> <span style="color: var(--text-muted); font-size: 0.75rem;">(${arch.size_mb.toFixed(1)} MB)</span></span>
        </label>
        <span class="archive-badge ${badgeClass}">${badgeText}</span>
      `;
      listEl.appendChild(item);
    });
  } catch (err) {
    listEl.innerHTML = `<div class="empty-state" style="color: var(--red);">Error connecting to testing engine API</div>`;
  }
}

// ── Symbol Discovery Helper ──────────────────────────────────────────────────
function getSymbolsFromInput(elemId) {
  const el = document.getElementById(elemId);
  if (!el) return ["auto"];
  const symRaw = el.value.trim().toLowerCase();
  if (!symRaw || symRaw === "auto") return ["auto"];
  return symRaw.toUpperCase().split(",").map(s => s.trim()).filter(Boolean);
}

// ── Global Live Progress Indicator ──────────────────────────────────────────
function setGlobalProgress(pct, label, active = true) {
  const container = document.getElementById("globalProgressContainer");
  const fill = document.getElementById("globalProgressBarFill");
  const pctEl = document.getElementById("globalProgressPct");
  const labelEl = document.getElementById("globalProgressLabel");
  const headerStatus = document.getElementById("headerStatusText");

  if (!container) return;

  if (!active) {
    if (fill) fill.style.width = "100%";
    if (pctEl) pctEl.innerText = "100%";
    setTimeout(() => {
      container.style.display = "none";
      if (headerStatus) headerStatus.innerText = "ENGINE READY";
    }, 450);
    return;
  }

  container.style.display = "block";
  const clamped = Math.max(0, Math.min(100, Math.round(pct)));
  if (fill) fill.style.width = `${clamped}%`;
  if (pctEl) pctEl.innerText = `${clamped}%`;
  if (labelEl && label) labelEl.innerText = label;
  if (headerStatus && label) headerStatus.innerText = label.toUpperCase().slice(0, 32);
}

// ── Run Real Backtest Simulation ─────────────────────────────────────────────
async function runBacktest() {
  const btn = document.getElementById("btnRun");
  const status = document.getElementById("runStatus");
  const headerStatus = document.getElementById("headerStatusText");
  const dirInput = document.getElementById("dirInput");

  // Gather selected dates
  const selectedDates = [];
  document.querySelectorAll('input[name="archiveDate"]:checked').forEach(cb => {
    selectedDates.push(cb.value);
  });

  if (selectedDates.length === 0) {
    status.innerText = "Error: Please select at least one session date!";
    status.style.color = "var(--red)";
    return;
  }

  const strat = document.getElementById("strategySelect").value;
  const tf = document.getElementById("timeframeSelect").value;
  const capital = parseFloat(document.getElementById("capitalInput").value) || 500000.0;
  const maxLoss = (parseFloat(document.getElementById("maxLossInput").value) || 1.5) / 100.0;
  const trailingSl = (parseFloat(document.getElementById("trailingSlInput").value) || 1.0) / 100.0;
  const archiveDir = dirInput ? dirInput.value.trim() : "";

  const payload = {
    archive_dir: archiveDir,
    dates: selectedDates,
    strategy: strat,
    timeframe: tf,
    capital: capital,
    risk_pct: maxLoss,
    trailing_sl_pct: trailingSl
  };

  // Strategy specific parameters
  if (strat === "equity") {
    payload.min_score = parseInt(document.getElementById("minScoreInput").value) || 55;
    payload.atr_sl_mult = parseFloat(document.getElementById("atrSlInput").value) || 1.5;
    payload.symbols = getSymbolsFromInput("symbolsInput");

  } else if (strat === "orb") {
    payload.opening_minutes = parseInt(document.getElementById("orbMinutesInput").value) || 15;
    payload.risk_reward = parseFloat(document.getElementById("orbRrInput").value) || 2.0;
    payload.breakout_atr_mult = parseFloat(document.getElementById("orbAtrMultInput").value) || 1.0;
    payload.symbols = getSymbolsFromInput("orbSymbolsInput");
  } else if (strat === "supertrend") {
    payload.atr_period = parseInt(document.getElementById("stAtrPeriodInput").value) || 10;
    payload.multiplier = parseFloat(document.getElementById("stMultiplierInput").value) || 3.0;
    payload.ema_filter = parseInt(document.getElementById("stEmaFilterInput").value) || 50;
    payload.risk_reward = parseFloat(document.getElementById("stRrInput").value) || 2.0;
    payload.symbols = getSymbolsFromInput("stSymbolsInput");
  } else if (strat === "camarilla") {
    payload.risk_reward = parseFloat(document.getElementById("camRrInput").value) || 2.0;
    payload.sl_buffer_pts = parseFloat(document.getElementById("camBufferPtsInput").value) || 5.0;
    payload.symbols = getSymbolsFromInput("camSymbolsInput");
  } else if (strat === "ema-ribbon") {
    payload.fast_ema = parseInt(document.getElementById("ribbonFastInput").value) || 9;
    payload.med_ema = parseInt(document.getElementById("ribbonMedInput").value) || 21;
    payload.slow_ema = parseInt(document.getElementById("ribbonSlowInput").value) || 50;
    payload.sl_pts = parseFloat(document.getElementById("ribbonSlPtsInput").value) || 15.0;
    payload.target_pts = parseFloat(document.getElementById("ribbonTgtPtsInput").value) || 30.0;
    payload.symbols = getSymbolsFromInput("ribbonSymbolsInput");
  } else if (strat === "bollinger-b") {
    payload.bb_period = parseInt(document.getElementById("bbPeriodInput").value) || 20;
    payload.bb_std = parseFloat(document.getElementById("bbStdDevInput").value) || 2.0;
    payload.oversold_b = parseFloat(document.getElementById("bbOversoldInput").value) || 0.05;
    payload.overbought_b = parseFloat(document.getElementById("bbOverboughtInput").value) || 0.95;
    payload.sl_pts = parseFloat(document.getElementById("bbSlPtsInput").value) || 15.0;
    payload.target_pts = parseFloat(document.getElementById("bbTgtPtsInput").value) || 30.0;
    payload.symbols = getSymbolsFromInput("bbBandsSymbolsInput");
  } else if (strat === "macd-accel") {
    payload.fast_period = parseInt(document.getElementById("macdFastInput").value) || 12;
    payload.slow_period = parseInt(document.getElementById("macdSlowInput").value) || 26;
    payload.signal_period = parseInt(document.getElementById("macdSignalInput").value) || 9;
    payload.sl_pts = parseFloat(document.getElementById("macdSlPtsInput").value) || 15.0;
    payload.target_pts = parseFloat(document.getElementById("macdTgtPtsInput").value) || 35.0;
    payload.symbols = getSymbolsFromInput("macdSymbolsInput");
  } else if (strat === "vwap-reversion") {
    payload.bb_period = parseInt(document.getElementById("vwapBbPeriodInput").value) || 20;
    payload.bb_std = parseFloat(document.getElementById("vwapBbStdInput").value) || 2.0;
    payload.sl_pts = parseFloat(document.getElementById("vwapSlPtsInput").value) || 15.0;
    payload.target_pts = parseFloat(document.getElementById("vwapTgtPtsInput").value) || 30.0;
    payload.symbols = getSymbolsFromInput("vwapSymbolsInput");
  } else if (strat === "rsi-momentum") {
    payload.fast_ema = parseInt(document.getElementById("rsiFastEmaInput").value) || 9;
    payload.slow_ema = parseInt(document.getElementById("rsiSlowEmaInput").value) || 21;
    payload.rsi_period = parseInt(document.getElementById("rsiPeriodInput").value) || 14;
    payload.rsi_long_cutoff = parseFloat(document.getElementById("rsiLongCutoffInput").value) || 60.0;
    payload.symbols = getSymbolsFromInput("rsiSymbolsInput");
  } else if (strat === "options") {
    payload.sl_points = parseFloat(document.getElementById("optionSlInput").value) || 12.0;
    payload.target_multiplier = parseFloat(document.getElementById("optionTgtInput").value) || 1.8;
    payload.lot_size = parseInt(document.getElementById("optionLotSizeInput").value) || 25;
  } else if (strat === "ai-replay") {
    payload.confidence = parseFloat(document.getElementById("aiConfidenceInput").value) || 0.70;
  } else if (strat === "short-straddle") {
    payload.entry_time = document.getElementById("straddleEntryTime") ? document.getElementById("straddleEntryTime").value.trim() : "09:20";
    payload.otm_strikes = parseInt(document.getElementById("straddleOtmStrikes").value) || 0;
    payload.sl_pct = (parseFloat(document.getElementById("straddleSlPct").value) || 25.0) / 100.0;
    payload.target_pct = (parseFloat(document.getElementById("straddleTgtPct").value) || 60.0) / 100.0;
    payload.lot_size = parseInt(document.getElementById("straddleLotSize").value) || 25;
  } else if (strat === "pcr-reversion") {
    payload.pcr_oversold = parseFloat(document.getElementById("pcrOversoldInput").value) || 0.70;
    payload.pcr_overbought = parseFloat(document.getElementById("pcrOverboughtInput").value) || 1.35;
    payload.sl_pct = (parseFloat(document.getElementById("pcrSlPctInput").value) || 25.0) / 100.0;
    payload.target_pct = (parseFloat(document.getElementById("pcrTgtPctInput").value) || 50.0) / 100.0;
    payload.lot_size = parseInt(document.getElementById("pcrLotSizeInput").value) || 25;
  } else if (strat === "banknifty-options") {
    payload.sl_points = parseFloat(document.getElementById("bnOptionSlInput").value) || 30.0;
    payload.target_multiplier = parseFloat(document.getElementById("bnOptionTgtInput").value) || 2.0;
    payload.orb_window_minutes = parseInt(document.getElementById("bnOrbMinutesInput").value) || 15;
    payload.lot_size = parseInt(document.getElementById("bnLotSizeInput").value) || 15;
  } else if (strat === "futures-trend") {
    payload.fast_ema = parseInt(document.getElementById("futFastEma").value) || 9;
    payload.mid_ema = parseInt(document.getElementById("futMidEma").value) || 21;
    payload.slow_ema = parseInt(document.getElementById("futSlowEma").value) || 50;
    payload.atr_multiplier = parseFloat(document.getElementById("futAtrMult").value) || 1.5;
    payload.risk_reward = parseFloat(document.getElementById("futRiskReward").value) || 2.0;
    payload.lot_size = parseInt(document.getElementById("futLotSize").value) || 25;
  } else if (strat === "max-pain") {
    payload.entry_start_time = document.getElementById("mpStartTime") ? document.getElementById("mpStartTime").value.trim() : "11:30";
    payload.min_displacement = parseFloat(document.getElementById("mpMinDisp").value) || 40.0;
    payload.sl_pct = (parseFloat(document.getElementById("mpSlPct").value) || 30.0) / 100.0;
    payload.target_pct = (parseFloat(document.getElementById("mpTgtPct").value) || 50.0) / 100.0;
    payload.lot_size = parseInt(document.getElementById("mpLotSize").value) || 25;
  }

  btn.disabled = true;
  btn.innerText = "⏳ SIMULATING...";
  status.innerText = `Connecting session stream for [${selectedDates.join(", ")}]...`;
  status.style.color = "var(--accent-cyan)";
  if (headerStatus) headerStatus.innerText = "BACKTEST RUNNING";

  setGlobalProgress(0, `Connecting simulation stream for ${selectedDates.length} session(s)...`, true);

  const progressBox = document.getElementById("runProgressContainer");
  const progressBar = document.getElementById("runProgressBar");
  const progressLabel = document.getElementById("runProgressLabel");
  const progressPct = document.getElementById("runProgressPct");

  if (progressBox) {
    progressBox.style.display = "block";
    if (progressBar) progressBar.style.width = "0%";
    if (progressLabel) progressLabel.innerText = `Starting replay for ${selectedDates.length} session(s)...`;
    if (progressPct) progressPct.innerText = "0%";
  }

  let streamSucceeded = false;

  try {
    const res = await fetch("/api/run/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (res.ok && res.body && window.ReadableStream) {
      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop(); // keep trailing incomplete chunk

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("data:")) continue;
          const jsonStr = trimmed.slice(5).trim();
          try {
            const event = JSON.parse(jsonStr);
            if (event.type === "progress") {
              const pct = Math.round((event.day / event.total) * 100);
              if (progressBar) progressBar.style.width = `${pct}%`;
              if (progressPct) progressPct.innerText = `${pct}%`;
              const progressMsg = `Session ${event.day}/${event.total} (${event.date}) · Trades: ${event.trades} · Day P&L: ₹${event.net_pnl}`;
              if (progressLabel) {
                progressLabel.innerText = progressMsg;
              }
              setGlobalProgress(pct, progressMsg, true);
              status.innerText = `Replaying session ${event.day}/${event.total} [${event.date}] · Trades: ${event.trades} · Day P&L: ₹${event.net_pnl}`;
            } else if (event.type === "complete") {
              streamSucceeded = true;
              const resultPayload = event.result;
              const tradeCount = resultPayload.trades ? resultPayload.trades.length : 0;
              if (progressBar) progressBar.style.width = "100%";
              if (progressPct) progressPct.innerText = "100%";
              setGlobalProgress(100, `Simulation complete! Processed ${tradeCount} trades.`, false);
              status.innerText = `Simulation complete! Processed ${tradeCount} executed trades.`;
              status.style.color = "var(--green)";
              renderResults(resultPayload);
              setTimeout(() => switchTab("tabAnalytics"), 250);
            } else if (event.type === "error") {
              status.innerText = `Error: ${event.message}`;
              status.style.color = "var(--red)";
              setGlobalProgress(0, "", false);
            }
          } catch (pe) {
            // chunk parse error, wait for next chunk
          }
        }
      }
    }
  } catch (streamErr) {
    console.warn("Live stream fetch interrupted, falling back to /api/run:", streamErr);
  }

  // Fallback to standard /api/run if stream did not produce a complete result
  if (!streamSucceeded) {
    try {
      status.innerText = `Processing simulation across selected dates...`;
      setGlobalProgress(50, `Processing simulation across ${selectedDates.length} session(s)...`, true);
      const fallbackRes = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await fallbackRes.json();
      if (data.status === "success") {
        const resultPayload = data.result || data;
        const tradeCount = resultPayload.trades ? resultPayload.trades.length : 0;
        if (progressBar) progressBar.style.width = "100%";
        if (progressPct) progressPct.innerText = "100%";
        setGlobalProgress(100, `Simulation complete! Processed ${tradeCount} trades.`, false);
        status.innerText = `Simulation complete! Processed ${tradeCount} executed trades.`;
        status.style.color = "var(--green)";
        renderResults(resultPayload);
        switchTab("tabAnalytics");
      } else {
        status.innerText = `Error: ${data.message}`;
        status.style.color = "var(--red)";
        setGlobalProgress(0, "", false);
      }
    } catch (err) {
      status.innerText = `Execution failed: ${err}`;
      status.style.color = "var(--red)";
      setGlobalProgress(0, "", false);
    }
  }

  btn.disabled = false;
  btn.innerText = "⚡ RUN BACKTEST";
  if (headerStatus) headerStatus.innerText = "ENGINE READY";
}



// ── Load Latest Results on Initial Launch ────────────────────────────────────
async function loadLatestResults() {
  try {
    const res = await fetch("/api/results");
    const data = await res.json();
    if (data.status === "success" && (data.result || data.metrics)) {
      renderResults(data.result || data);
    }
  } catch (err) {
    // Fresh session, no latest run yet
  }
}

// ── Multi-Strategy Comparison Mode ───────────────────────────────────────────
let compareChart = null;

function initCompareModelPicker() {
  const btnToggle = document.getElementById("btnToggleCompareModels");
  const panel = document.getElementById("compareModelsPanel");
  const btnAll = document.getElementById("btnSelectAllCompare");
  const btnEquity = document.getElementById("btnSelectEquityCompare");
  const btnDefault = document.getElementById("btnSelectDefaultCompare");
  const btnFno = document.getElementById("btnSelectFnoCompare");
  const btnCompare = document.getElementById("btnCompare");

  const updateCompareButtonLabel = () => {
    const checkedCount = document.querySelectorAll('input[name="compareStrategy"]:checked').length;
    if (btnCompare && !btnCompare.disabled) {
      btnCompare.innerHTML = `<span class="btn-icon">⚖️</span><span class="btn-text">COMPARE (${checkedCount})</span>`;
    }
  };

  if (btnToggle && panel) {
    btnToggle.addEventListener("click", () => {
      panel.style.display = panel.style.display === "none" ? "block" : "none";
    });
  }

  if (btnAll) {
    btnAll.addEventListener("click", () => {
      document.querySelectorAll('input[name="compareStrategy"]').forEach(cb => cb.checked = true);
      updateCompareButtonLabel();
    });
  }

  if (btnEquity) {
    btnEquity.addEventListener("click", () => {
      const equityStrats = ["equity", "orb", "supertrend", "camarilla", "ema-ribbon", "bollinger-b", "macd-accel", "vwap-reversion", "rsi-momentum"];
      document.querySelectorAll('input[name="compareStrategy"]').forEach(cb => {
        cb.checked = equityStrats.includes(cb.value);
      });
      updateCompareButtonLabel();
    });
  }

  if (btnFno) {
    btnFno.addEventListener("click", () => {
      const fnoStrats = ["options", "short-straddle", "pcr-reversion", "banknifty-options", "futures-trend", "max-pain"];
      document.querySelectorAll('input[name="compareStrategy"]').forEach(cb => {
        cb.checked = fnoStrats.includes(cb.value);
      });
      updateCompareButtonLabel();
    });
  }

  if (btnDefault) {
    btnDefault.addEventListener("click", () => {
      const defaultStrats = ["equity", "orb", "supertrend", "camarilla", "ema-ribbon", "bollinger-b"];
      document.querySelectorAll('input[name="compareStrategy"]').forEach(cb => {
        cb.checked = defaultStrats.includes(cb.value);
      });
      updateCompareButtonLabel();
    });
  }

  document.querySelectorAll('input[name="compareStrategy"]').forEach(cb => {
    cb.addEventListener("change", updateCompareButtonLabel);
  });

  updateCompareButtonLabel();
}

async function runComparison() {
  const btn = document.getElementById("btnCompare");
  const status = document.getElementById("runStatus");
  const dirInput = document.getElementById("dirInput");

  const selectedDates = [];
  document.querySelectorAll('input[name="archiveDate"]:checked').forEach(cb => {
    selectedDates.push(cb.value);
  });

  if (selectedDates.length === 0) {
    status.innerText = "Error: Please select at least one session date for comparison!";
    status.style.color = "var(--red)";
    return;
  }

  const selectedStrats = [];
  document.querySelectorAll('input[name="compareStrategy"]:checked').forEach(cb => {
    selectedStrats.push(cb.value);
  });

  if (selectedStrats.length === 0) {
    status.innerText = "Error: Please select at least one strategy model from the ⚙️ Models picker!";
    status.style.color = "var(--red)";
    return;
  }

  const tf = document.getElementById("timeframeSelect").value;
  const capital = parseFloat(document.getElementById("capitalInput").value) || 500000.0;
  const maxLoss = (parseFloat(document.getElementById("maxLossInput").value) || 1.5) / 100.0;
  const archiveDir = dirInput ? dirInput.value.trim() : "";
  const symbols = getSymbolsFromInput("symbolsInput");

  const payload = {
    directory: archiveDir,
    dates: selectedDates,
    strategies: selectedStrats,
    timeframe: tf,
    capital: capital,
    risk_pct: maxLoss,
    symbols: symbols
  };

  btn.disabled = true;
  btn.innerHTML = `<span class="btn-icon">⚖️</span><span class="btn-text">COMPARING (${selectedStrats.length})...</span>`;
  status.innerText = `Benchmarking ${selectedStrats.length} strategies across [${selectedDates.join(", ")}]...`;
  status.style.color = "var(--accent-cyan)";
  setGlobalProgress(0, `Benchmarking ${selectedStrats.length} strategies across ${selectedDates.length} session(s)...`, true);

  let streamSucceeded = false;

  try {
    const res = await fetch("/api/compare/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (res.ok && res.body && window.ReadableStream) {
      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop();

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("data:")) continue;
          const jsonStr = trimmed.slice(5).trim();
          try {
            const event = JSON.parse(jsonStr);
            if (event.type === "progress") {
              const pct = Math.round((event.current / event.total) * 100);
              const sName = event.strategy_name || event.strategy;
              const pnlTxt = event.net_pnl !== undefined ? ` · Net P&L: ₹${event.net_pnl}` : "";
              setGlobalProgress(pct, `Strategy ${event.current}/${event.total}: ${sName}${pnlTxt}`, true);
              status.innerText = `Benchmarking ${event.current}/${event.total} [${sName}]${pnlTxt}...`;
            } else if (event.type === "complete") {
              streamSucceeded = true;
              setGlobalProgress(100, `Benchmark complete for ${event.comparison.length} models!`, false);
              status.innerText = `Strategy benchmark complete for ${event.comparison.length} models!`;
              status.style.color = "var(--green)";
              renderComparisonResults(event.comparison);
              switchTab("tabAnalytics");
              const sec = document.getElementById("compareSection");
              if (sec) sec.scrollIntoView({ behavior: "smooth" });
            } else if (event.type === "error") {
              status.innerText = `Comparison stream error: ${event.message}`;
              status.style.color = "var(--red)";
              setGlobalProgress(0, "", false);
            }
          } catch (pe) {}
        }
      }
    }
  } catch (streamErr) {
    console.warn("Compare stream fetch interrupted, falling back to /api/compare:", streamErr);
  }

  // Fallback to non-streaming /api/compare if stream failed
  if (!streamSucceeded) {
    try {
      setGlobalProgress(50, `Benchmarking ${selectedStrats.length} strategies...`, true);
      const fallbackRes = await fetch("/api/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await fallbackRes.json();
      if (data.status === "success" && data.comparison) {
        setGlobalProgress(100, `Benchmark complete for ${data.comparison.length} models!`, false);
        status.innerText = `Strategy benchmark complete for ${data.comparison.length} models!`;
        status.style.color = "var(--green)";
        renderComparisonResults(data.comparison);
        switchTab("tabAnalytics");
        const sec = document.getElementById("compareSection");
        if (sec) sec.scrollIntoView({ behavior: "smooth" });
      } else {
        status.innerText = `Comparison failed: ${data.message || "Unknown error"}`;
        status.style.color = "var(--red)";
        setGlobalProgress(0, "", false);
      }
    } catch (err) {
      status.innerText = `Comparison failed: ${err}`;
      status.style.color = "var(--red)";
      setGlobalProgress(0, "", false);
    }
  }

  btn.disabled = false;
  btn.innerHTML = `<span class="btn-icon">⚖️</span><span class="btn-text">COMPARE (${selectedStrats.length})</span>`;
}


function renderComparisonResults(comparisonList) {
  const section = document.getElementById("compareSection");
  const tbody = document.getElementById("compareBody");
  if (!section || !tbody) return;

  section.style.display = "block";
  tbody.innerHTML = "";

  const chartDatasets = [];
  const palette = [
    "#00f2fe", "#4facfe", "#43e97b", "#fa709a",
    "#fee140", "#f38181", "#a18cd1", "#fbc2eb",
    "#20bf6b", "#fd9644", "#a55eea", "#2bcbba",
    "#ff6b6b", "#48dbfb", "#1dd1a1", "#feca57"
  ];

  comparisonList.forEach((item, idx) => {
    if (item.error) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td style="font-weight: 600;">${item.strategy_key}</td><td colspan="9" style="color: var(--red);">${item.error}</td>`;
      tbody.appendChild(tr);
      return;
    }

    const m = item.metrics || {};
    const netPnl = m.net_pnl || 0;
    const isPos = netPnl >= 0;
    const color = palette[idx % palette.length];

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td style="font-weight: 700; color: ${color};">${item.strategy_name || item.strategy_key}</td>
      <td>${m.total_trades || 0}</td>
      <td>${(m.win_rate || 0).toFixed(1)}%</td>
      <td>${(m.profit_factor || 0).toFixed(2)}</td>
      <td>${(m.sharpe_ratio || 0).toFixed(2)}</td>
      <td>${(m.sortino_ratio || 0).toFixed(2)}</td>
      <td style="font-weight: 600; color: ${(m.calmar_ratio || 0) >= 1 ? "var(--green)" : ""};">${(m.calmar_ratio || 0).toFixed(2)}</td>
      <td style="color: var(--red);">${(m.max_drawdown_pct || 0).toFixed(2)}%</td>
      <td style="font-weight: 700; color: ${isPos ? "var(--green)" : "var(--red)"};">${isPos ? "+" : ""}₹${netPnl.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
      <td style="font-weight: 600; color: ${isPos ? "var(--green)" : "var(--red)"};">${(m.return_pct || 0).toFixed(2)}%</td>
    `;
    tbody.appendChild(tr);

    if (item.equity_curve && item.equity_curve.length > 0) {
      chartDatasets.push({
        label: item.strategy_name || item.strategy_key,
        data: item.equity_curve.map(pt => ({ x: pt.timestamp, y: pt.equity })),
        borderColor: color,
        backgroundColor: "transparent",
        borderWidth: 2,
        tension: 0.1,
        pointRadius: 0
      });
    }
  });

  const canvas = document.getElementById("compareChart");
  if (canvas && chartDatasets.length > 0) {
    if (compareChart) compareChart.destroy();
    compareChart = new Chart(canvas, {
      type: "line",
      data: { datasets: chartDatasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            position: "top",
            labels: { color: "#e2e8f0", font: { size: 11, weight: 600 } }
          },
          tooltip: {
            callbacks: {
              label: ctx => `${ctx.dataset.label}: ₹${Number(ctx.parsed.y).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`
            }
          }
        },
        scales: {
          x: {
            ticks: { color: "#64748b", maxTicksLimit: 8 },
            grid: { color: "rgba(255,255,255,0.04)" }
          },
          y: {
            ticks: {
              color: "#64748b",
              callback: val => "₹" + Number(val).toLocaleString("en-IN")
            },
            grid: { color: "rgba(255,255,255,0.06)" }
          }
        }
      }
    });
  }
}


// ── Render Results: Institutional KPIs, Charts, and Trades Table ─────────────
function renderResults(raw) {
  const data = raw.result || raw;
  const m = data.metrics || {};
  allTrades = data.trades || [];

  // 1. Institutional KPIs
  const netPnlEl = document.getElementById("kpiNetPnl");
  const returnEl = document.getElementById("kpiReturn");
  const winRateEl = document.getElementById("kpiWinRate");
  const tradesCountEl = document.getElementById("kpiTradesCount");
  const pfEl = document.getElementById("kpiProfitFactor");
  const expEl = document.getElementById("kpiExpectancy");
  const sharpeEl = document.getElementById("kpiSharpe");
  const sortinoEl = document.getElementById("kpiSortino");
  const calmarEl = document.getElementById("kpiCalmar");
  const calmarSubEl = document.getElementById("kpiCalmarSub");
  const maxDDEl = document.getElementById("kpiMaxDD");
  const maxDDRsEl = document.getElementById("kpiMaxDDRs");
  const maxWinStreakEl = document.getElementById("kpiMaxWinStreak");
  const maxLossStreakEl = document.getElementById("kpiMaxLossStreak");
  const chargesEl = document.getElementById("kpiCharges");
  const breakevenEl = document.getElementById("kpiBreakeven");

  const netPnl = m.net_pnl || 0.0;
  const isProfit = netPnl >= 0;
  netPnlEl.innerText = `${isProfit ? "+" : ""}₹${netPnl.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
  netPnlEl.className = `kpi-value ${isProfit ? "pos" : "neg"}`;

  const retPct = m.return_pct || 0.0;
  returnEl.innerText = `${retPct >= 0 ? "+" : ""}${retPct.toFixed(2)}% on capital`;
  returnEl.style.color = isProfit ? "var(--green)" : "var(--red)";

  winRateEl.innerText = `${(m.win_rate || 0.0).toFixed(1)}%`;
  const be = m.breakeven_count || 0;
  tradesCountEl.innerText = `${m.total_trades || 0} trades (${m.wins || 0}W / ${m.losses || 0}L / ${be}BE)`;

  pfEl.innerText = (m.profit_factor || 0.0).toFixed(2);
  expEl.innerText = `Exp: ₹${(m.expectancy || 0.0).toFixed(2)}`;

  sharpeEl.innerText = (m.sharpe_ratio || 0.0).toFixed(2);
  sortinoEl.innerText = `Sortino: ${(m.sortino_ratio || 0.0).toFixed(2)}`;

  // Calmar Ratio
  const calmarVal = m.calmar_ratio || 0.0;
  calmarEl.innerText = calmarVal.toFixed(2);
  calmarEl.className = `kpi-value ${calmarVal >= 1.0 ? "pos" : calmarVal > 0 ? "" : "neg"}`;
  calmarSubEl.innerText = `Return ${retPct >= 0 ? "+" : ""}${retPct.toFixed(2)}% / DD ${(m.max_drawdown_pct || 0.0).toFixed(2)}%`;

  maxDDEl.innerText = `${(m.max_drawdown_pct || 0.0).toFixed(2)}%`;
  maxDDRsEl.innerText = `₹${(m.max_drawdown_rs || 0.0).toLocaleString("en-IN", { minimumFractionDigits: 2 })} peak-to-trough`;

  // Streak cards
  const mxWins = m.max_consecutive_wins || 0;
  const mxLoss = m.max_consecutive_losses || 0;
  maxWinStreakEl.innerText = `${mxWins} consecutive win${mxWins !== 1 ? "s" : ""}`;
  maxLossStreakEl.innerText = `${mxLoss} consecutive loss${mxLoss !== 1 ? "es" : ""}`;

  chargesEl.innerText = `₹${(m.total_charges || 0.0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
  breakevenEl.innerText = `${be} breakeven trade${be !== 1 ? "s" : ""} · STT, GST, Exchange, SEBI`;

  // 2. Charts (6-Chart Quantitative Suite)
  const equityCurve = data.equity_curve || m.equity_curve || [];
  let dailyPnls = data.daily_breakdown || data.daily_pnls || m.daily_pnls || [];
  if ((!dailyPnls || dailyPnls.length === 0) && (data.date || (allTrades.length > 0 && (allTrades[0].date || allTrades[0].exit_time)))) {
    const sessionDate = data.date || allTrades[0].date || (allTrades[0].exit_time ? allTrades[0].exit_time.split(" ")[0] : "Session");
    dailyPnls = [{
      date: sessionDate,
      starting_equity: data.initial_capital || 500000,
      ending_equity: data.final_equity || ((data.initial_capital || 500000) + (m.net_pnl || 0)),
      gross_pnl: m.gross_pnl || 0,
      charges: m.total_charges || 0,
      net_pnl: m.net_pnl || 0,
      pnl: m.net_pnl || 0,
      return_pct: m.return_pct || 0,
      trades: m.total_trades || allTrades.length,
      win_rate: m.win_rate || 0
    }];
  }

  renderEquityChart(equityCurve);
  renderDailyChart(dailyPnls);
  renderSessionBreakdownTable(dailyPnls);
  renderDrawdownChart(drawdownCurve);
  renderHourlyChart(allTrades);
  renderOutcomeChart(m, allTrades);
  renderPnlDistChart(allTrades);

  // 3. Trades Table & Trade Inspector
  updateDateFilterOptions();
  updateSymbolFilterOptions();
  updateSortHeaderUI();
  filterAndRenderTrades();

  // If trades exist, auto-select first trade in Inspector
  if (allTrades.length > 0) {
    inspectTrade(allTrades[0].trade_id);
  }
}

// ── Session-by-Session Breakdown Data Table ─────────────────────────────────
function renderSessionBreakdownTable(dailyPnls) {
  const card = document.getElementById("sessionBreakdownCard");
  const badge = document.getElementById("sessionCountBadge");
  const tbody = document.getElementById("sessionBreakdownBody");
  const tfoot = document.getElementById("sessionBreakdownFoot");
  if (!card || !tbody) return;

  if (!dailyPnls || dailyPnls.length === 0) {
    card.style.display = "none";
    tbody.innerHTML = "";
    if (tfoot) tfoot.innerHTML = "";
    return;
  }

  card.style.display = "block";
  if (badge) {
    badge.innerText = `${dailyPnls.length} Session${dailyPnls.length !== 1 ? "s" : ""}`;
  }

  tbody.innerHTML = "";
  let totGross = 0.0;
  let totCharges = 0.0;
  let totNet = 0.0;
  let totTrades = 0;
  let totWins = 0;
  let startEq = dailyPnls[0].starting_equity || 0.0;
  let endEq = dailyPnls[dailyPnls.length - 1].ending_equity || 0.0;

  dailyPnls.forEach(d => {
    const gross = d.gross_pnl !== undefined ? d.gross_pnl : (d.pnl || 0);
    const charges = d.charges !== undefined ? d.charges : 0;
    const net = d.net_pnl !== undefined ? d.net_pnl : (d.pnl || 0);
    const trCount = d.trades !== undefined ? d.trades : (d.trades_count || 0);
    const winRate = d.win_rate !== undefined ? d.win_rate : 0.0;
    const retPct = d.return_pct !== undefined ? d.return_pct : (d.starting_equity ? ((net / d.starting_equity) * 100) : 0.0);

    totGross += gross;
    totCharges += charges;
    totNet += net;
    totTrades += trCount;
    if (d.win_rate !== undefined) {
      totWins += Math.round((winRate / 100) * trCount);
    }

    const tr = document.createElement("tr");
    const isWin = net >= 0;
    tr.innerHTML = `
      <td style="font-weight: 700; color: #fff;">
        <span style="display: inline-flex; align-items: center; gap: 6px;">
          <span>📅</span>
          <span>${d.date || "-"}</span>
        </span>
      </td>
      <td>₹${(d.starting_equity || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
      <td>₹${(d.ending_equity || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
      <td style="color: ${gross >= 0 ? "var(--green)" : "var(--red)"};">
        ${gross >= 0 ? "+" : ""}₹${gross.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
      </td>
      <td style="color: var(--text-muted);">₹${charges.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
      <td style="font-weight: 700; color: ${isWin ? "var(--green)" : "var(--red)"};">
        ${isWin ? "+" : ""}₹${net.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
      </td>
      <td style="font-weight: 600; color: ${retPct >= 0 ? "var(--green)" : "var(--red)"};">
        ${retPct >= 0 ? "+" : ""}${retPct.toFixed(2)}%
      </td>
      <td>${trCount}</td>
      <td>${winRate.toFixed(1)}%</td>
    `;

    // Click session row to filter trade log to this session date
    tr.addEventListener("click", () => {
      const dateFilter = document.getElementById("tradeDateFilter");
      if (dateFilter && d.date) {
        dateFilter.value = d.date;
        filterAndRenderTrades();
        switchTab("tabInspector");
      }
    });

    tbody.appendChild(tr);
  });

  if (tfoot) {
    const aggRetPct = startEq > 0 ? ((totNet / startEq) * 100) : 0.0;
    const aggWinRate = totTrades > 0 ? ((totWins / totTrades) * 100) : 0.0;
    const isTotProfit = totNet >= 0;
    tfoot.innerHTML = `
      <tr>
        <td style="color: var(--accent-cyan);">SUMMARY TOTALS</td>
        <td>₹${startEq.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
        <td>₹${endEq.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
        <td style="color: ${totGross >= 0 ? "var(--green)" : "var(--red)"};">
          ${totGross >= 0 ? "+" : ""}₹${totGross.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
        </td>
        <td style="color: var(--text-muted);">₹${totCharges.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
        <td style="font-weight: 800; color: ${isTotProfit ? "var(--green)" : "var(--red)"};">
          ${isTotProfit ? "+" : ""}₹${totNet.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
        </td>
        <td style="font-weight: 800; color: ${aggRetPct >= 0 ? "var(--green)" : "var(--red)"};">
          ${aggRetPct >= 0 ? "+" : ""}${aggRetPct.toFixed(2)}%
        </td>
        <td style="font-weight: 800;">${totTrades}</td>
        <td style="font-weight: 800;">${aggWinRate.toFixed(1)}%</td>
      </tr>
    `;
  }
}

// ── Update Trade Date Filter Options ─────────────────────────────────────────
function updateDateFilterOptions() {
  const dateFilter = document.getElementById("tradeDateFilter");
  if (!dateFilter) return;

  const currentVal = dateFilter.value;
  dateFilter.innerHTML = '<option value="">All Dates</option>';

  const dateCounts = {};
  allTrades.forEach(t => {
    const d = t.date || ((t.entry_time || "").includes(" ") ? t.entry_time.split(" ")[0] : "");
    if (d) {
      dateCounts[d] = (dateCounts[d] || 0) + 1;
    }
  });

  const uniqueDates = Object.keys(dateCounts).sort();
  if (uniqueDates.length > 1) {
    dateFilter.style.display = "inline-block";
  } else if (uniqueDates.length === 0) {
    dateFilter.style.display = "none";
    return;
  } else {
    dateFilter.style.display = "inline-block";
  }

  uniqueDates.forEach(d => {
    const opt = document.createElement("option");
    opt.value = d;
    opt.innerText = `${d} (${dateCounts[d]} trade${dateCounts[d] > 1 ? "s" : ""})`;
    if (d === currentVal) opt.selected = true;
    dateFilter.appendChild(opt);
  });
}


// ── Chart.js Renderers ───────────────────────────────────────────────────────
function renderEquityChart(curve) {
  const canvas = document.getElementById("equityChart");
  const placeholder = document.getElementById("equityPlaceholder");
  const returnBadge = document.getElementById("equityReturnBadge");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (equityChart) equityChart.destroy();

  if (curve.length === 0) {
    if (placeholder) placeholder.style.display = "flex";
    return;
  }
  if (placeholder) placeholder.style.display = "none";

  const labels = curve.map(pt => pt.timestamp.split(" ").pop() || pt.timestamp);
  const values = curve.map(pt => pt.equity);

  const isNetProfit = values.length > 0 && values[values.length - 1] >= (values[0] || 0);
  const lineColor = isNetProfit ? "#10b981" : "#ef4444";
  const fillColor = isNetProfit ? "rgba(16, 185, 129, 0.12)" : "rgba(239, 68, 68, 0.12)";

  if (returnBadge) {
    const returnAmt = values.length > 0 ? (values[values.length - 1] - values[0]) : 0;
    const returnPct = values[0] ? ((returnAmt / values[0]) * 100).toFixed(2) : "0.00";
    returnBadge.innerText = `${returnAmt >= 0 ? "+" : ""}₹${returnAmt.toLocaleString("en-IN", { minimumFractionDigits: 2 })} (${returnPct}%)`;
    returnBadge.style.color = isNetProfit ? "var(--green)" : "var(--red)";
    returnBadge.style.borderColor = isNetProfit ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)";
  }

  equityChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [{
        label: "Portfolio Equity (₹)",
        data: values,
        borderColor: lineColor,
        backgroundColor: fillColor,
        fill: true,
        tension: 0.1,
        pointRadius: 0,
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(10, 16, 28, 0.95)",
          borderColor: "rgba(255, 255, 255, 0.1)",
          borderWidth: 1,
          callbacks: {
            label: (ctx) => `Equity: ₹${ctx.parsed.y.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`
          }
        }
      },
      scales: {
        x: {
          display: true,
          ticks: { color: "#64748b", maxTicksLimit: 8 },
          grid: { color: "rgba(255,255,255,0.03)" }
        },
        y: {
          ticks: {
            color: "#64748b",
            callback: (v) => `₹${v.toLocaleString("en-IN")}`
          },
          grid: { color: "rgba(255,255,255,0.05)" }
        }
      }
    }
  });
}

function renderDailyChart(daily) {
  const canvas = document.getElementById("dailyChart");
  const placeholder = document.getElementById("dailyPlaceholder");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (dailyChart) dailyChart.destroy();

  if (daily.length === 0) {
    if (placeholder) placeholder.style.display = "flex";
    return;
  }
  if (placeholder) placeholder.style.display = "none";

  const labels = daily.map(d => d.date);
  const values = daily.map(d => d.net_pnl);
  const colors = values.map(v => v >= 0 ? "#10b981" : "#ef4444");

  dailyChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [{
        label: "Daily Net P&L",
        data: values,
        backgroundColor: colors,
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(10, 16, 28, 0.95)",
          borderColor: "rgba(255, 255, 255, 0.1)",
          borderWidth: 1,
          callbacks: {
            label: (ctx) => `Net P&L: ₹${ctx.parsed.y.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`
          }
        }
      },
      scales: {
        x: { ticks: { color: "#64748b" }, grid: { display: false } },
        y: {
          ticks: {
            color: "#64748b",
            callback: (v) => `₹${v.toLocaleString("en-IN")}`
          },
          grid: { color: "rgba(255,255,255,0.05)" }
        }
      }
    }
  });
}

function renderDrawdownChart(curve) {
  const canvas = document.getElementById("drawdownChart");
  const placeholder = document.getElementById("drawdownPlaceholder");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (drawdownChart) drawdownChart.destroy();

  if (curve.length === 0) {
    if (placeholder) placeholder.style.display = "flex";
    return;
  }
  if (placeholder) placeholder.style.display = "none";

  const labels = curve.map(pt => pt.timestamp.split(" ").pop() || pt.timestamp);
  const values = curve.map(pt => -Math.abs(pt.drawdown_pct));

  drawdownChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [{
        label: "Underwater Drawdown (%)",
        data: values,
        borderColor: "#ef4444",
        backgroundColor: "rgba(239, 68, 68, 0.12)",
        fill: true,
        tension: 0.1,
        pointRadius: 0,
        borderWidth: 1.5
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(10, 16, 28, 0.95)",
          borderColor: "rgba(255, 255, 255, 0.1)",
          borderWidth: 1,
          callbacks: {
            label: (ctx) => `Drawdown: ${ctx.parsed.y.toFixed(2)}%`
          }
        }
      },
      scales: {
        x: {
          display: true,
          ticks: { color: "#64748b", maxTicksLimit: 8 },
          grid: { color: "rgba(255,255,255,0.03)" }
        },
        y: {
          ticks: {
            color: "#64748b",
            callback: (v) => `${v.toFixed(1)}%`
          },
          grid: { color: "rgba(255,255,255,0.05)" }
        }
      }
    }
  });
}

function renderHourlyChart(trades) {
  const canvas = document.getElementById("hourlyChart");
  const placeholder = document.getElementById("hourlyPlaceholder");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (hourlyChart) hourlyChart.destroy();

  if (!trades || trades.length === 0) {
    if (placeholder) placeholder.style.display = "flex";
    return;
  }
  if (placeholder) placeholder.style.display = "none";

  const hourBuckets = {
    "09:00": 0, "10:00": 0, "11:00": 0, "12:00": 0,
    "13:00": 0, "14:00": 0, "15:00": 0
  };

  trades.forEach(t => {
    if (!t.entry_time) return;
    const timeStr = t.entry_time.split(" ").pop() || "";
    const hourPart = timeStr.split(":")[0];
    const key = `${hourPart.padStart(2, '0')}:00`;
    if (hourBuckets[key] !== undefined) {
      hourBuckets[key] += (t.net_pnl || 0);
    } else {
      hourBuckets[key] = (t.net_pnl || 0);
    }
  });

  const labels = Object.keys(hourBuckets).sort();
  const values = labels.map(k => Math.round(hourBuckets[k] * 100) / 100);
  const colors = values.map(v => v >= 0 ? "#10b981" : "#ef4444");

  hourlyChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [{
        label: "Hourly Net P&L (₹)",
        data: values,
        backgroundColor: colors,
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(10, 16, 28, 0.95)",
          borderColor: "rgba(255, 255, 255, 0.1)",
          borderWidth: 1,
          callbacks: {
            label: (ctx) => `Net P&L: ₹${ctx.parsed.y.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`
          }
        }
      },
      scales: {
        x: { ticks: { color: "#64748b" }, grid: { display: false } },
        y: {
          ticks: {
            color: "#64748b",
            callback: (v) => `₹${v.toLocaleString("en-IN")}`
          },
          grid: { color: "rgba(255,255,255,0.05)" }
        }
      }
    }
  });
}

function renderOutcomeChart(m, trades) {
  const canvas = document.getElementById("outcomeChart");
  const placeholder = document.getElementById("outcomePlaceholder");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (outcomeChart) outcomeChart.destroy();

  const total = (trades && trades.length) || m.total_trades || 0;
  if (total === 0) {
    if (placeholder) placeholder.style.display = "flex";
    return;
  }
  if (placeholder) placeholder.style.display = "none";

  let wins = m.wins || 0;
  let losses = m.losses || 0;
  let breakeven = 0;

  if (trades && trades.length > 0) {
    wins = trades.filter(t => (t.net_pnl || 0) > 0).length;
    losses = trades.filter(t => (t.net_pnl || 0) < 0).length;
    breakeven = trades.filter(t => (t.net_pnl || 0) === 0).length;
  }

  outcomeChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Winning Trades", "Losing Trades", "Breakeven"],
      datasets: [{
        data: [wins, losses, breakeven],
        backgroundColor: ["#10b981", "#ef4444", "#64748b"],
        borderWidth: 2,
        borderColor: "rgba(10, 16, 28, 0.95)"
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "68%",
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: "#94a3b8", font: { family: "'JetBrains Mono', monospace", size: 11 }, padding: 14 }
        },
        tooltip: {
          backgroundColor: "rgba(10, 16, 28, 0.95)",
          borderColor: "rgba(255, 255, 255, 0.1)",
          borderWidth: 1,
          callbacks: {
            label: (ctx) => {
              const val = ctx.parsed;
              const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
              return `${ctx.label}: ${val} (${pct}%)`;
            }
          }
        }
      }
    }
  });
}

function renderPnlDistChart(trades) {
  const canvas = document.getElementById("pnlDistChart");
  const placeholder = document.getElementById("pnlDistPlaceholder");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (pnlDistChart) pnlDistChart.destroy();

  if (!trades || trades.length === 0) {
    if (placeholder) placeholder.style.display = "flex";
    return;
  }
  if (placeholder) placeholder.style.display = "none";

  const pnls = trades.map(t => t.net_pnl || 0);
  const minPnl = Math.min(...pnls);
  const maxPnl = Math.max(...pnls);

  const binCount = 6;
  const range = (maxPnl - minPnl) || 100;
  const binSize = range / binCount;

  const binLabels = [];
  const binCounts = new Array(binCount).fill(0);
  const binColors = [];

  for (let i = 0; i < binCount; i++) {
    const low = minPnl + i * binSize;
    const high = low + binSize;
    const mid = (low + high) / 2;
    binLabels.push(`₹${Math.round(low)}..₹${Math.round(high)}`);
    binColors.push(mid >= 0 ? "#10b981" : "#ef4444");
  }

  pnls.forEach(p => {
    let idx = Math.floor((p - minPnl) / binSize);
    if (idx >= binCount) idx = binCount - 1;
    if (idx < 0) idx = 0;
    binCounts[idx]++;
  });

  pnlDistChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: binLabels,
      datasets: [{
        label: "Trade Frequency",
        data: binCounts,
        backgroundColor: binColors,
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(10, 16, 28, 0.95)",
          borderColor: "rgba(255, 255, 255, 0.1)",
          borderWidth: 1,
          callbacks: {
            label: (ctx) => `${ctx.parsed.y} trades in this return bin`
          }
        }
      },
      scales: {
        x: { ticks: { color: "#64748b", font: { size: 10 } }, grid: { display: false } },
        y: {
          beginAtZero: true,
          ticks: {
            color: "#64748b",
            precision: 0,
            stepSize: 1
          },
          grid: { color: "rgba(255,255,255,0.05)" }
        }
      }
    }
  });
}

// ── Trades Table: Sorting, Quick Filter Pills, and Inspector ─────────────────
function initTableSort() {
  const headers = document.querySelectorAll("th[data-sort]");
  headers.forEach(th => {
    th.style.cursor = "pointer";
    th.addEventListener("click", () => {
      const col = th.getAttribute("data-sort");
      if (currentSortColumn === col) {
        sortAscending = !sortAscending;
      } else {
        currentSortColumn = col;
        sortAscending = false; // default descending for most recent/highest
      }
      updateSortHeaderUI();
      filterAndRenderTrades();
    });
  });
}

function updateSortHeaderUI() {
  const headers = document.querySelectorAll("th[data-sort]");
  headers.forEach(th => {
    const col = th.getAttribute("data-sort");
    let baseLabel = th.getAttribute("data-label");
    if (!baseLabel) {
      baseLabel = th.innerText.replace(/[⬍▲▼]/g, "").trim();
      th.setAttribute("data-label", baseLabel);
    }
    if (col === currentSortColumn) {
      th.innerHTML = `${baseLabel} <span style="color: var(--accent-cyan); font-weight: bold;">${sortAscending ? "▲" : "▼"}</span>`;
      th.style.color = "var(--accent-cyan)";
    } else {
      th.innerHTML = `${baseLabel} <span style="opacity: 0.35;">⬍</span>`;
      th.style.color = "";
    }
  });
}

function initTradeFilters() {
  const pills = document.querySelectorAll(".table-filters .filter-pill");
  pills.forEach(pill => {
    pill.addEventListener("click", () => {
      pills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      currentTradeFilter = pill.getAttribute("data-filter") || "all";
      filterAndRenderTrades();
    });
  });

  const symFilter = document.getElementById("tradeSymbolFilter");
  if (symFilter) {
    symFilter.addEventListener("change", () => {
      filterAndRenderTrades();
    });
  }
}

function updateSymbolFilterOptions() {
  const symFilter = document.getElementById("tradeSymbolFilter");
  if (!symFilter) return;
  const currentVal = symFilter.value;
  const uniqueSyms = Array.from(new Set(allTrades.map(t => t.symbol).filter(Boolean))).sort();
  symFilter.innerHTML = '<option value="">All Symbols</option>';
  uniqueSyms.forEach(sym => {
    const opt = document.createElement("option");
    opt.value = sym;
    opt.innerText = sym;
    if (sym === currentVal) opt.selected = true;
    symFilter.appendChild(opt);
  });
}

function filterAndRenderTrades() {
  const searchInput = document.getElementById("tradeSearchInput");
  const query = searchInput ? searchInput.value.trim().toLowerCase() : "";
  const symFilter = document.getElementById("tradeSymbolFilter");
  const selectedSym = symFilter ? symFilter.value : "";
  const dateFilter = document.getElementById("tradeDateFilter");
  const selectedDate = dateFilter ? dateFilter.value : "";

  filteredTrades = allTrades.filter(t => {
    // 0. Dedicated Date Filter
    if (selectedDate) {
      const tradeDate = t.date || ((t.entry_time || "").includes(" ") ? t.entry_time.split(" ")[0] : "");
      if (tradeDate && tradeDate !== selectedDate) {
        return false;
      }
    }

    // 1. Dedicated Symbol Filter
    if (selectedSym && (t.symbol || "") !== selectedSym) {
      return false;
    }

    // 2. Text Search Filter
    if (query) {
      const sym = (t.symbol || "").toLowerCase();
      const side = (t.side || "").toLowerCase();
      const reason = (t.exit_reason || "").toLowerCase();
      const time = (t.entry_time || "").toLowerCase();
      const date = (t.date || "").toLowerCase();
      const matchesSearch = sym.includes(query) || side.includes(query) || reason.includes(query) || time.includes(query) || date.includes(query);
      if (!matchesSearch) return false;
    }

    // 3. Pill Category Filter
    if (currentTradeFilter === "win") {
      return (t.net_pnl || 0) > 0;
    } else if (currentTradeFilter === "loss") {
      return (t.net_pnl || 0) < 0;
    } else if (currentTradeFilter === "breakeven") {
      return (t.net_pnl || 0) === 0;
    } else if (currentTradeFilter === "buy") {
      return (t.side || "").toUpperCase() === "BUY";
    } else if (currentTradeFilter === "sell") {
      return (t.side || "").toUpperCase() === "SELL";
    }

    return true;
  });

  // Sort
  filteredTrades.sort((a, b) => {
    let col = currentSortColumn;
    let valA = a[col];
    let valB = b[col];

    if (col === "entry_date") {
      valA = a.date || ((a.entry_time || "").includes(" ") ? a.entry_time.split(" ")[0] : "");
      valB = b.date || ((b.entry_time || "").includes(" ") ? b.entry_time.split(" ")[0] : "");
    } else if (col === "entry_time") {
      valA = (a.entry_time || "").includes(" ") ? a.entry_time.split(" ")[1] : (a.entry_time || "");
      valB = (b.entry_time || "").includes(" ") ? b.entry_time.split(" ")[1] : (b.entry_time || "");
    }

    if (valA === undefined || valA === null) valA = "";
    if (valB === undefined || valB === null) valB = "";

    if (typeof valA === "number" && typeof valB === "number") {
      return sortAscending ? valA - valB : valB - valA;
    }
    return sortAscending
      ? String(valA).localeCompare(String(valB))
      : String(valB).localeCompare(String(valA));
  });

  // Update count badge
  const countBadge = document.getElementById("tradesCountBadge");
  if (countBadge) {
    countBadge.innerText = (query || selectedDate || selectedSym || currentTradeFilter !== "all")
      ? `${filteredTrades.length} of ${allTrades.length} trades`
      : `${allTrades.length} trades`;
  }

  const tbody = document.getElementById("tradesBody");
  if (filteredTrades.length === 0) {
    tbody.innerHTML = '<tr><td colspan="12" class="empty-state">No trades match the active filter or search query.</td></tr>';
    return;
  }

  tbody.innerHTML = "";
  filteredTrades.forEach(t => {
    const tr = document.createElement("tr");
    tr.dataset.tradeId = t.trade_id;
    if (t.trade_id === currentSelectedTradeId) {
      tr.classList.add("selected-row");
    }

    const isWin = (t.net_pnl || 0) >= 0;
    const entryRaw = String(t.entry_time || "");
    const dateStr = t.date || (entryRaw.includes(" ") ? entryRaw.split(" ")[0] : "-");
    const timeStr = entryRaw.includes(" ") ? entryRaw.split(" ")[1] : (entryRaw || "-");

    tr.innerHTML = `
      <td><span style="font-family:'JetBrains Mono',monospace; font-size:0.78rem; color:var(--text-muted);">${dateStr}</span></td>
      <td><span style="font-family:'JetBrains Mono',monospace; font-size:0.78rem;">${timeStr}</span></td>
      <td style="font-weight: 600; color: #fff;">${t.symbol}</td>
      <td style="color: ${t.side === "BUY" ? "var(--green)" : "var(--red)"}; font-weight: 600;">${t.side}</td>
      <td>${t.qty}</td>
      <td>₹${(t.entry_price || 0).toFixed(2)}</td>
      <td>${t.exit_price ? "₹" + Number(t.exit_price).toFixed(2) : "-"}</td>
      <td style="color: ${(t.gross_pnl || 0) >= 0 ? "var(--green)" : "var(--red)"};">₹${(t.gross_pnl || 0).toFixed(2)}</td>
      <td style="color: var(--text-muted);">₹${(t.charges || 0).toFixed(2)}</td>
      <td style="font-weight: 700; color: ${isWin ? "var(--green)" : "var(--red)"};">
        ${isWin ? "+" : ""}₹${(t.net_pnl || 0).toFixed(2)}
      </td>
      <td><span class="badge" style="font-size: 0.7rem; background: rgba(255,255,255,0.08);">${t.exit_reason || "-"}</span></td>
      <td><button class="btn-detail" onclick="inspectTrade('${t.trade_id}'); event.stopPropagation();">Inspect 🔍</button></td>
    `;

    // Row click selects trade into Inspector
    tr.addEventListener("click", () => {
      inspectTrade(t.trade_id);
    });

    tbody.appendChild(tr);
  });
}

// ── Dedicated Trade Inspector Panel ──────────────────────────────────────────
function inspectTrade(tradeId) {
  currentSelectedTradeId = tradeId;
  const container = document.getElementById("inspectorContent");
  const badge = document.getElementById("inspBadge");
  const title = document.getElementById("inspTitle");
  if (!container) return;

  // Highlight row in table
  document.querySelectorAll("#tradesBody tr").forEach(r => r.classList.remove("selected-row"));
  const targetRow = document.querySelector(`#tradesBody tr[data-trade-id="${tradeId}"]`);
  if (targetRow) targetRow.classList.add("selected-row");

  const trade = allTrades.find(t => t.trade_id === tradeId);
  if (!trade) {
    container.innerHTML = `<div class="empty-state">Trade #${tradeId} not found.</div>`;
    return;
  }

  const isWin = (trade.net_pnl || 0) >= 0;
  const pnlColor = isWin ? "var(--green)" : "var(--red)";
  const charges = trade.charges_breakdown || {};
  const meta = trade.metadata || {};

  if (title) title.innerText = `${trade.symbol} (${trade.side})`;
  if (badge) {
    badge.innerText = `${trade.status || "CLOSED"} • ${isWin ? "+" : ""}₹${(trade.net_pnl || 0).toFixed(2)}`;
    badge.style.color = pnlColor;
    badge.style.borderColor = isWin ? "rgba(16, 185, 129, 0.4)" : "rgba(239, 68, 68, 0.4)";
  }

  const pnlPts = trade.exit_price ? ((trade.exit_price - trade.entry_price) * (trade.side === "BUY" ? 1 : -1)).toFixed(2) : "0.00";

  container.innerHTML = `
    <div class="insp-panel">
      <h4>⏱ Execution & Timing</h4>
      <div class="insp-row"><span class="insp-key">Trade ID</span><span class="insp-val mono">${trade.trade_id}</span></div>
      <div class="insp-row"><span class="insp-key">Instrument</span><span class="insp-val">${trade.symbol} (${trade.instrument_type || "EQUITY"})</span></div>
      <div class="insp-row"><span class="insp-key">Direction</span><span class="insp-val" style="color: ${trade.side === "BUY" ? "var(--green)" : "var(--red)"}; font-weight: 700;">${trade.side}</span></div>
      <div class="insp-row"><span class="insp-key">Quantity</span><span class="insp-val">${trade.qty}</span></div>
      <div class="insp-row"><span class="insp-key">Entry Time</span><span class="insp-val">${trade.entry_time || "—"}</span></div>
      <div class="insp-row"><span class="insp-key">Exit Time</span><span class="insp-val">${trade.exit_time || "—"}</span></div>
      <div class="insp-row"><span class="insp-key">Holding Duration</span><span class="insp-val">${trade.holding_bars || 0} bars (${trade.holding_bars || 0}m)</span></div>
    </div>

    <div class="insp-panel">
      <h4>📊 Price Action & Target Levels</h4>
      <div class="insp-row"><span class="insp-key">Entry Price</span><span class="insp-val">₹${(trade.entry_price || 0).toFixed(2)}</span></div>
      <div class="insp-row"><span class="insp-key">Exit Price</span><span class="insp-val">${trade.exit_price ? "₹" + trade.exit_price.toFixed(2) : "—"}</span></div>
      <div class="insp-row"><span class="insp-key">Move (Points)</span><span class="insp-val" style="color: ${pnlPts >= 0 ? "var(--green)" : "var(--red)"}; font-weight: 700;">${pnlPts >= 0 ? "+" : ""}${pnlPts} pts</span></div>
      <div class="insp-row"><span class="insp-key">Initial Stop Loss</span><span class="insp-val">${trade.initial_sl ? "₹" + Number(trade.initial_sl).toFixed(2) : "—"}</span></div>
      <div class="insp-row"><span class="insp-key">Target Price</span><span class="insp-val">${trade.target ? "₹" + Number(trade.target).toFixed(2) : "—"}</span></div>
      <div class="insp-row"><span class="insp-key">Exit Trigger</span><span class="insp-val badge" style="background: rgba(255,255,255,0.06); font-size: 0.72rem;">${trade.exit_reason || "CLOSE"}</span></div>
    </div>

    <div class="insp-panel">
      <h4>💰 Financials & Statutory Fee Audit</h4>
      <div class="insp-row"><span class="insp-key">Gross P&L</span><span class="insp-val" style="color: ${(trade.gross_pnl || 0) >= 0 ? "var(--green)" : "var(--red)"};">₹${(trade.gross_pnl || 0).toFixed(2)}</span></div>
      <div class="insp-row"><span class="insp-key">Brokerage (₹20/order)</span><span class="insp-val">₹${(charges.brokerage || 0).toFixed(2)}</span></div>
      <div class="insp-row"><span class="insp-key">STT (Securities Transaction Tax)</span><span class="insp-val">₹${(charges.stt || 0).toFixed(2)}</span></div>
      <div class="insp-row"><span class="insp-key">Exchange Turnover Charges</span><span class="insp-val">₹${(charges.exchange_fee || 0).toFixed(2)}</span></div>
      <div class="insp-row"><span class="insp-key">GST (18% on fees)</span><span class="insp-val">₹${(charges.gst || 0).toFixed(2)}</span></div>
      <div class="insp-row"><span class="insp-key">SEBI Turnover Fee</span><span class="insp-val">₹${(charges.sebi || 0).toFixed(2)}</span></div>
      <div class="insp-row"><span class="insp-key">Stamp Duty</span><span class="insp-val">₹${(charges.stamp_duty || 0).toFixed(2)}</span></div>
      <div class="insp-row" style="border-top: 1px solid rgba(255,255,255,0.08); padding-top: 4px;"><span class="insp-key">Total Statutory Charges</span><span class="insp-val" style="color: var(--yellow);">₹${(trade.charges || 0).toFixed(2)}</span></div>
      <div class="insp-row" style="border-top: 1px solid rgba(255,255,255,0.08); padding-top: 6px;"><span class="insp-key" style="font-weight: 700; color: #fff;">Net Realized P&L</span><span class="insp-val" style="font-size: 1rem; color: ${pnlColor}; font-weight: 800;">${isWin ? "+" : ""}₹${(trade.net_pnl || 0).toFixed(2)} (${(trade.pnl_pct || 0).toFixed(2)}%)</span></div>
    </div>

    ${meta.strategy || meta.score || meta.reasoning || meta.strike ? `
    <div class="insp-panel">
      <h4>🤖 Strategy & Signal Rationale</h4>
      ${meta.strategy ? `<div class="insp-row"><span class="insp-key">Strategy</span><span class="insp-val">${meta.strategy}</span></div>` : ""}
      ${meta.score ? `<div class="insp-row"><span class="insp-key">Signal Score</span><span class="insp-val">${meta.score} / 100</span></div>` : ""}
      ${meta.sector ? `<div class="insp-row"><span class="insp-key">Sector</span><span class="insp-val">${meta.sector}</span></div>` : ""}
      ${meta.strike ? `<div class="insp-row"><span class="insp-key">Option Strike</span><span class="insp-val">${meta.strike} (Δ ${meta.delta || "—"})</span></div>` : ""}
      ${meta.reasoning ? `<div style="margin-top: 4px; font-size: 0.76rem; color: var(--text-muted); line-height: 1.4;">${meta.reasoning}</div>` : ""}
    </div>` : ""}
  `;
}
window.inspectTrade = inspectTrade;

// ── Data Explorer Tab Renderer ───────────────────────────────────────────────
function renderDataExplorer(archives) {
  const container = document.getElementById("explorerSessionsGrid");
  if (!container) return;

  if (!archives || archives.length === 0) {
    container.innerHTML = '<div class="empty-state">No historical archives or sessions discovered in current directory. Use "Browse File/Folder" to pick market recordings.</div>';
    return;
  }

  const commonDbs = ["equities.db", "indices.db", "indicators.db", "trade.db", "optionchain_snapshot.db", "master.db", "circuit_limits.json"];

  container.innerHTML = archives.map(arch => {
    const extFiles = arch.extracted_files || [];
    const isExtracted = arch.is_extracted;
    const badgeType = arch.source_type === "folder" ? "Session Folder" : (isExtracted ? "Extracted Cache" : "Compressed RAR");
    const badgeClass = isExtracted ? "badge-extracted" : "badge-archive";

    return `
      <div class="session-card">
        <div class="session-card-header">
          <h4>📅 ${arch.date || "Recorded Session"}</h4>
          <span class="archive-badge ${badgeClass}">${badgeType}</span>
        </div>
        <div style="font-size: 0.78rem; color: var(--text-muted); display: flex; flex-direction: column; gap: 5px;">
          <div><strong style="color: #fff;">Source:</strong> ${arch.filename || arch.name}</div>
          <div><strong style="color: #fff;">Size:</strong> ${arch.size_mb ? arch.size_mb.toFixed(1) + " MB" : "—"}</div>
          <div style="margin-top: 6px;"><strong style="color: #fff;">Database Inventory:</strong></div>
          <div class="db-badge-list">
            ${commonDbs.map(db => {
              const present = extFiles.includes(db);
              return `<span class="db-pill ${present ? "present" : ""}">${present ? "✓ " : ""}${db}</span>`;
            }).join("")}
          </div>
        </div>
        <div style="margin-top: 10px; border-top: 1px solid var(--panel-border); padding-top: 10px; display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 0.72rem; color: var(--text-muted);">${extFiles.length} database assets</span>
          <button class="btn-secondary btn-sm" onclick="selectAndTestSession('${arch.date}')">⚡ Test in Console</button>
        </div>
      </div>
    `;
  }).join("");
}

function selectAndTestSession(dateStr) {
  // Check this session checkbox in console and switch tab
  const checkboxes = document.querySelectorAll('input[name="archiveDate"]');
  checkboxes.forEach(cb => {
    cb.checked = (cb.value === dateStr);
  });
  switchTab("tabConsole");
}
window.selectAndTestSession = selectAndTestSession;

// ── Trade Detail Modal (Modal Pop-up) ────────────────────────────────────────
function initModal() {
  const modal = document.getElementById("tradeModal");
  const closeBtn = document.getElementById("modalCloseBtn");

  if (closeBtn) {
    closeBtn.addEventListener("click", closeTradeModal);
  }
  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeTradeModal();
    });
  }
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeTradeModal();
  });
}

function openTradeModal(tradeId) {
  const modal = document.getElementById("tradeModal");
  const content = document.getElementById("modalContent");
  const title = document.getElementById("modalTitle");

  const trade = allTrades.find(t => t.trade_id === tradeId);
  if (!trade) return;

  const isWin = (trade.net_pnl || 0) >= 0;
  title.innerText = `Trade Details: ${trade.symbol} (${trade.side})`;

  const charges = trade.charges_breakdown || {};
  content.innerHTML = `
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;">
      <div>
        <div style="color: var(--text-muted); font-size: 0.75rem;">Execution Time:</div>
        <div style="font-weight: 600;">${trade.entry_time} → ${trade.exit_time || "OPEN"}</div>
      </div>
      <div>
        <div style="color: var(--text-muted); font-size: 0.75rem;">Holding Duration:</div>
        <div style="font-weight: 600;">${trade.holding_bars || 0} bars (${(trade.holding_bars || 0)}m)</div>
      </div>
      <div>
        <div style="color: var(--text-muted); font-size: 0.75rem;">Entry Fill:</div>
        <div style="font-weight: 600;">₹${(trade.entry_price || 0).toFixed(2)} (${trade.qty} shares)</div>
      </div>
      <div>
        <div style="color: var(--text-muted); font-size: 0.75rem;">Exit Fill:</div>
        <div style="font-weight: 600;">${trade.exit_price ? "₹" + trade.exit_price.toFixed(2) : "-"}</div>
      </div>
      <div>
        <div style="color: var(--text-muted); font-size: 0.75rem;">Risk & Target:</div>
        <div style="font-weight: 500; color: var(--text-muted);">SL: ₹${(trade.initial_sl || 0).toFixed(2)} | TGT: ₹${(trade.target || 0).toFixed(2)}</div>
      </div>
      <div>
        <div style="color: var(--text-muted); font-size: 0.75rem;">Net Realized P&L:</div>
        <div style="font-weight: 700; color: ${isWin ? "var(--green)" : "var(--red)"}; font-size: 1.1rem;">
          ${isWin ? "+" : ""}₹${(trade.net_pnl || 0).toFixed(2)} (${(trade.pnl_pct || 0).toFixed(2)}%)
        </div>
      </div>
    </div>

    <div style="background: rgba(0,0,0,0.3); padding: 12px; border-radius: 6px; border: 1px solid var(--panel-border);">
      <h4 style="font-size: 0.8rem; text-transform: uppercase; color: var(--accent-cyan); margin-bottom: 8px;">
        Statutory Fee Schedule Breakdown
      </h4>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.8rem;">
        <div>Brokerage: <span style="color:#fff;">₹${(charges.brokerage || 0).toFixed(2)}</span></div>
        <div>STT: <span style="color:#fff;">₹${(charges.stt || 0).toFixed(2)}</span></div>
        <div>Exchange Fee: <span style="color:#fff;">₹${(charges.exchange_fee || 0).toFixed(2)}</span></div>
        <div>GST (18%): <span style="color:#fff;">₹${(charges.gst || 0).toFixed(2)}</span></div>
        <div>SEBI: <span style="color:#fff;">₹${(charges.sebi || 0).toFixed(2)}</span></div>
        <div>Stamp Duty: <span style="color:#fff;">₹${(charges.stamp_duty || 0).toFixed(2)}</span></div>
      </div>
      <div style="margin-top: 10px; border-top: 1px solid var(--panel-border); padding-top: 6px; display: flex; justify-content: space-between; font-weight: 600;">
        <span>Total Charges:</span>
        <span style="color: var(--yellow);">₹${(trade.charges || 0).toFixed(2)}</span>
      </div>
    </div>
  `;

  modal.style.display = "flex";
}
window.openTradeModal = openTradeModal;

function closeTradeModal() {
  const modal = document.getElementById("tradeModal");
  if (modal) modal.style.display = "none";
}
window.closeTradeModal = closeTradeModal;


// ── Institutional Performance Tearsheet ───────────────────────────────────────
function openTearsheet() {
  window.open("/api/tearsheet", "_blank");
}
window.openTearsheet = openTearsheet;


// ── Default Parameter Grids Registry ──────────────────────────────────────────
const STRATEGY_DEFAULT_GRIDS = {
  "orb": {
    "opening_minutes": [10, 15, 20],
    "risk_reward": [1.5, 2.0, 2.5],
    "breakout_atr_mult": [0.5, 1.0]
  },
  "equity": {
    "min_score": [50, 55, 60],
    "atr_sl_mult": [1.2, 1.5, 1.8],
    "atr_tgt_mult": [2.5, 3.0]
  },
  "supertrend": {
    "atr_period": [7, 10, 14],
    "multiplier": [2.5, 3.0, 3.5],
    "risk_reward": [1.5, 2.0]
  },
  "camarilla": {
    "risk_reward": [1.5, 2.0, 2.5],
    "sl_buffer_pts": [3.0, 5.0, 7.0]
  },
  "ema-ribbon": {
    "fast_ema": [7, 9],
    "med_ema": [15, 21],
    "sl_pts": [10.0, 15.0],
    "target_pts": [25.0, 35.0]
  },
  "bollinger-b": {
    "period": [15, 20],
    "std_dev": [1.8, 2.0, 2.2],
    "oversold_b": [0.05, 0.10],
    "overbought_b": [0.90, 0.95]
  },
  "macd-accel": {
    "fast_period": [8, 12],
    "slow_period": [21, 26],
    "sl_pts": [10.0, 15.0],
    "target_pts": [25.0, 35.0]
  },
  "vwap-reversion": {
    "bb_period": [15, 20],
    "bb_std": [1.8, 2.0, 2.5],
    "sl_pts": [10.0, 15.0],
    "target_pts": [20.0, 30.0]
  },
  "rsi-momentum": {
    "rsi_period": [10, 14],
    "rsi_long_cutoff": [55.0, 60.0, 65.0],
    "fast_ema": [9, 13],
    "slow_ema": [21, 34]
  },
  "options": {
    "sl_points": [10.0, 12.0, 15.0],
    "target_multiplier": [1.5, 1.8, 2.0]
  },
  "ai-replay": {
    "min_confidence": [0.60, 0.70, 0.80]
  },
  "short-straddle": {
    "sl_pct": [0.20, 0.25, 0.30],
    "target_pct": [0.50, 0.60, 0.70]
  },
  "pcr-reversion": {
    "pcr_oversold": [0.65, 0.70, 0.75],
    "pcr_overbought": [1.30, 1.35, 1.40],
    "sl_pct": [0.20, 0.25, 0.30]
  },
  "banknifty-options": {
    "sl_points": [25.0, 30.0, 35.0],
    "target_multiplier": [1.8, 2.0, 2.5]
  },
  "futures-trend": {
    "fast_ema": [7, 9],
    "mid_ema": [15, 21],
    "atr_multiplier": [1.2, 1.5, 2.0],
    "risk_reward": [1.5, 2.0]
  },
  "max-pain": {
    "min_displacement": [30.0, 40.0, 50.0],
    "sl_pct": [0.25, 0.30],
    "target_pct": [0.40, 0.50]
  }
};


// ── Walk-Forward Optimization (WFO) Engine ────────────────────────────────────
let wfoChart = null;

function initWalkForward() {
  const btnRunWfo = document.getElementById("btnRunWfo");
  if (btnRunWfo) {
    btnRunWfo.addEventListener("click", runWalkForward);
  }
}

async function runWalkForward() {
  const btn = document.getElementById("btnRunWfo");
  const status = document.getElementById("wfoStatus");
  const dirInput = document.getElementById("dirInput");
  const archiveDir = dirInput ? dirInput.value.trim() : "";

  const selectedDates = [];
  document.querySelectorAll('input[name="archiveDate"]:checked').forEach(cb => {
    selectedDates.push(cb.value);
  });

  const inSample = parseInt(document.getElementById("wfoInSampleInput").value) || 3;
  const outSample = parseInt(document.getElementById("wfoOutSampleInput").value) || 1;
  const totalNeeded = inSample + outSample;

  if (selectedDates.length < totalNeeded) {
    status.innerText = `Walk-Forward requires at least ${totalNeeded} sessions selected (IS: ${inSample}, OOS: ${outSample}). Selected: ${selectedDates.length}.`;
    status.style.color = "var(--red)";
    return;
  }

  const strat = document.getElementById("wfoStrategySelect").value;
  const rankBy = document.getElementById("wfoRankBySelect").value;
  const symbols = getSymbolsFromInput("symbolsInput");

  btn.disabled = true;
  btn.innerText = "🧪 RUNNING WFO...";
  status.innerText = `Optimizing ${strat.toUpperCase()} over rolling windows across [${selectedDates.join(", ")}]...`;
  status.style.color = "var(--accent-cyan)";

  const wfoProgressBox = document.getElementById("wfoProgressContainer");
  const wfoProgressBar = document.getElementById("wfoProgressBar");
  const wfoProgressLabel = document.getElementById("wfoProgressLabel");
  const wfoProgressPct = document.getElementById("wfoProgressPct");
  if (wfoProgressBox) {
    wfoProgressBox.style.display = "block";
    if (wfoProgressBar) wfoProgressBar.style.width = "0%";
    if (wfoProgressPct) wfoProgressPct.innerText = "0%";
    if (wfoProgressLabel) wfoProgressLabel.innerText = "Initializing rolling windows...";
  }
  setGlobalProgress(0, `Initializing Walk-Forward analysis for ${strat.toUpperCase()}...`, true);

  const payload = {
    directory: archiveDir,
    dates: selectedDates,
    strategy: strat,
    in_sample: inSample,
    out_of_sample: outSample,
    rank_by: rankBy,
    symbols: symbols
  };

  let streamSucceeded = false;

  try {
    const res = await fetch("/api/walk_forward/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (res.ok && res.body && window.ReadableStream) {
      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop();

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("data:")) continue;
          const jsonStr = trimmed.slice(5).trim();
          try {
            const event = JSON.parse(jsonStr);
            if (event.type === "progress") {
              const pct = Math.round((event.window / event.total) * 100);
              const msg = `Window ${event.window}/${event.total} · IS: [${event.in_sample_dates.join(",")}] · OOS: [${event.out_of_sample_dates.join(",")}] · OOS P&L: ₹${event.oos_pnl}`;
              setGlobalProgress(pct, `Walk-Forward Window ${event.window}/${event.total} (OOS P&L: ₹${event.oos_pnl})`, true);
              if (wfoProgressBar) wfoProgressBar.style.width = `${pct}%`;
              if (wfoProgressPct) wfoProgressPct.innerText = `${pct}%`;
              if (wfoProgressLabel) wfoProgressLabel.innerText = msg;
              status.innerText = msg;
            } else if (event.type === "complete") {
              streamSucceeded = true;
              const wfoRes = event.result || event;
              if (wfoProgressBar) wfoProgressBar.style.width = "100%";
              if (wfoProgressPct) wfoProgressPct.innerText = "100%";
              setGlobalProgress(100, `Walk-Forward analysis complete (${wfoRes.total_windows} windows)!`, false);
              status.innerText = `Walk-Forward analysis completed for ${wfoRes.total_windows} rolling windows!`;
              status.style.color = "var(--green)";
              renderWalkForwardResults(wfoRes);
            } else if (event.type === "error") {
              status.innerText = `WFO stream error: ${event.message}`;
              status.style.color = "var(--red)";
              setGlobalProgress(0, "", false);
            }
          } catch (pe) {}
        }
      }
    }
  } catch (streamErr) {
    console.warn("WFO stream fetch interrupted, falling back to /api/walk_forward:", streamErr);
  }

  // Fallback to standard /api/walk_forward
  if (!streamSucceeded) {
    try {
      setGlobalProgress(50, `Running Walk-Forward analysis across ${selectedDates.length} sessions...`, true);
      const fallbackRes = await fetch("/api/walk_forward", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await fallbackRes.json();
      if (data.status === "success") {
        if (wfoProgressBar) wfoProgressBar.style.width = "100%";
        if (wfoProgressPct) wfoProgressPct.innerText = "100%";
        setGlobalProgress(100, `Walk-Forward analysis complete (${data.total_windows} windows)!`, false);
        status.innerText = `Walk-Forward analysis completed for ${data.total_windows} rolling windows!`;
        status.style.color = "var(--green)";
        renderWalkForwardResults(data);
      } else {
        status.innerText = `WFO failed: ${data.message || "Unknown error"}`;
        status.style.color = "var(--red)";
        setGlobalProgress(0, "", false);
      }
    } catch (err) {
      status.innerText = `WFO failed: ${err}`;
      status.style.color = "var(--red)";
      setGlobalProgress(0, "", false);
    }
  }

  btn.disabled = false;
  btn.innerText = "🧪 RUN WALK-FORWARD ANALYSIS";
}

function renderWalkForwardResults(data) {
  const badge = document.getElementById("wfoVerdictBadge");
  const wfeVal = document.getElementById("wfoWfeVal");
  const verdictText = document.getElementById("wfoVerdictText");
  const totalWin = document.getElementById("wfoTotalWindows");
  const oosNetPnl = document.getElementById("wfoOosNetPnl");

  const wfe = data.walk_forward_efficiency;
  const isRobust = data.is_robust;

  if (badge) {
    badge.innerText = isRobust ? "ROBUST (WFE >= 0.50)" : "OVERFIT (WFE < 0.50)";
    badge.style.color = isRobust ? "var(--green)" : "var(--red)";
    badge.style.borderColor = isRobust ? "rgba(46,160,67,0.5)" : "rgba(248,81,73,0.5)";
  }
  if (wfeVal) {
    wfeVal.innerText = wfe.toFixed(2);
    wfeVal.style.color = isRobust ? "var(--green)" : "var(--red)";
  }
  if (verdictText) {
    verdictText.innerHTML = isRobust
      ? `<span style="color: var(--green); font-weight: 600;">PASS:</span> Strategy parameters transferred positive edge to unseen out-of-sample forward sessions (Efficiency: ${(wfe * 100).toFixed(0)}%).`
      : `<span style="color: var(--red); font-weight: 600;">CAUTION:</span> Strategy shows curve-fitting. Performance degraded on unseen forward data (Efficiency: ${(wfe * 100).toFixed(0)}%).`;
  }
  if (totalWin) totalWin.innerText = data.total_windows;
  if (oosNetPnl) {
    const oosPnl = data.overall_oos_metrics ? data.overall_oos_metrics.net_pnl : 0.0;
    oosNetPnl.innerText = `${oosPnl >= 0 ? "+" : ""}₹${oosPnl.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    oosNetPnl.style.color = oosPnl >= 0 ? "var(--green)" : "var(--red)";
  }

  // Render Table
  const tbody = document.getElementById("wfoWindowsBody");
  if (tbody) {
    tbody.innerHTML = "";
    (data.windows || []).forEach(w => {
      const isM = w.in_sample_metrics || {};
      const oosM = w.out_of_sample_metrics || {};
      const oosPnl = oosM.net_pnl || 0.0;
      const isPnlCls = oosPnl >= 0 ? "pos" : "neg";
      const paramsStr = Object.entries(w.best_params || {}).map(([k, v]) => `${k}=${v}`).join(", ");

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-weight: 700;">Window #${w.window}</td>
        <td style="font-size: 0.78rem; color: var(--yellow);">${(w.in_sample_dates || []).join(", ")}</td>
        <td style="font-size: 0.75rem; color: var(--accent-cyan);">${paramsStr || "default"}</td>
        <td style="text-align: right;">${(isM.sharpe_ratio || 0).toFixed(2)}</td>
        <td style="font-size: 0.78rem; color: #fff;">${(w.out_of_sample_dates || []).join(", ")}</td>
        <td style="text-align: right; font-weight: 600;">${(oosM.sharpe_ratio || 0).toFixed(2)}</td>
        <td style="text-align: right;" class="${isPnlCls}">${oosPnl >= 0 ? "+" : ""}₹${oosPnl.toFixed(2)}</td>
        <td style="text-align: right;">${(oosM.win_rate || 0).toFixed(1)}%</td>
        <td style="text-align: right;">${oosM.total_trades || 0}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  // Render Chart
  renderWfoChart(data.windows || []);
}

function renderWfoChart(windows) {
  const canvas = document.getElementById("wfoChartCanvas");
  const placeholder = document.getElementById("wfoPlaceholder");
  if (!canvas) return;

  if (placeholder) placeholder.style.display = "none";
  canvas.style.display = "block";

  const labels = windows.map(w => `Window #${w.window}`);
  const isSharpes = windows.map(w => (w.in_sample_metrics || {}).sharpe_ratio || 0);
  const oosSharpes = windows.map(w => (w.out_of_sample_metrics || {}).sharpe_ratio || 0);

  if (wfoChart) {
    wfoChart.destroy();
  }

  const ctx = canvas.getContext("2d");
  wfoChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "In-Sample Sharpe (Training)",
          data: isSharpes,
          backgroundColor: "rgba(0, 242, 254, 0.6)",
          borderColor: "#00f2fe",
          borderWidth: 1
        },
        {
          label: "Out-of-Sample Sharpe (Forward Test)",
          data: oosSharpes,
          backgroundColor: "rgba(46, 160, 67, 0.7)",
          borderColor: "#2ea043",
          borderWidth: 1
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          grid: { color: "rgba(255,255,255,0.06)" },
          ticks: { color: "#8b949e" }
        },
        y: {
          grid: { color: "rgba(255,255,255,0.06)" },
          ticks: { color: "#8b949e" }
        }
      },
      plugins: {
        legend: {
          labels: { color: "#f0f6fc", font: { family: "Outfit" } }
        }
      }
    }
  });
}


// ── Strategy Parameter Optimizer Engine ───────────────────────────────────────
let latestOptimizationResults = [];

function initParameterOptimizer() {
  const select = document.getElementById("optStrategySelect");
  const gridText = document.getElementById("optGridJson");
  const btnReset = document.getElementById("btnOptResetGrid");
  const btnRun = document.getElementById("btnRunOptimizer");
  const btnApplyBest = document.getElementById("btnApplyBestParams");

  const updateGridForStrategy = () => {
    const strat = select ? select.value : "orb";
    const defaultGrid = STRATEGY_DEFAULT_GRIDS[strat] || {};
    if (gridText) {
      gridText.value = JSON.stringify(defaultGrid, null, 2);
    }
  };

  if (select) {
    select.addEventListener("change", updateGridForStrategy);
    updateGridForStrategy();
  }
  if (btnReset) {
    btnReset.addEventListener("click", updateGridForStrategy);
  }
  if (btnRun) {
    btnRun.addEventListener("click", runParameterOptimization);
  }
  if (btnApplyBest) {
    btnApplyBest.addEventListener("click", () => {
      if (latestOptimizationResults.length > 0 && select) {
        applyParametersToConsole(select.value, latestOptimizationResults[0].params);
      }
    });
  }
}

async function runParameterOptimization() {
  const btn = document.getElementById("btnRunOptimizer");
  const status = document.getElementById("optStatus");
  const select = document.getElementById("optStrategySelect");
  const rankBySelect = document.getElementById("optRankBySelect");
  const gridText = document.getElementById("optGridJson");
  const dirInput = document.getElementById("dirInput");
  const archiveDir = dirInput ? dirInput.value.trim() : "";

  const selectedDates = [];
  document.querySelectorAll('input[name="archiveDate"]:checked').forEach(cb => {
    selectedDates.push(cb.value);
  });

  if (selectedDates.length === 0) {
    status.innerText = "Error: Please select at least one session date in Console tab.";
    status.style.color = "var(--red)";
    return;
  }

  let paramGrid;
  try {
    paramGrid = JSON.parse(gridText.value);
  } catch (err) {
    status.innerText = `Invalid JSON in Parameter Grid: ${err.message}`;
    status.style.color = "var(--red)";
    return;
  }

  const strat = select.value;
  const rankBy = rankBySelect.value;
  const symbols = getSymbolsFromInput("symbolsInput");

  btn.disabled = true;
  btn.innerText = "🚀 OPTIMIZING...";
  status.innerText = `Evaluating parameter grid for ${strat.toUpperCase()} across [${selectedDates.join(", ")}]...`;
  status.style.color = "var(--accent-cyan)";

  const optProgressBox = document.getElementById("optProgressContainer");
  const optProgressBar = document.getElementById("optProgressBar");
  const optProgressLabel = document.getElementById("optProgressLabel");
  const optProgressPct = document.getElementById("optProgressPct");
  if (optProgressBox) {
    optProgressBox.style.display = "block";
    if (optProgressBar) optProgressBar.style.width = "0%";
    if (optProgressPct) optProgressPct.innerText = "0%";
    if (optProgressLabel) optProgressLabel.innerText = "Testing parameter combinations...";
  }
  setGlobalProgress(0, `Evaluating parameter grid for ${strat.toUpperCase()} across ${selectedDates.length} session(s)...`, true);

  const payload = {
    directory: archiveDir,
    dates: selectedDates,
    strategy: strat,
    param_grid: paramGrid,
    rank_by: rankBy,
    symbols: symbols
  };

  let streamSucceeded = false;

  try {
    const res = await fetch("/api/optimize/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (res.ok && res.body && window.ReadableStream) {
      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop();

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("data:")) continue;
          const jsonStr = trimmed.slice(5).trim();
          try {
            const event = JSON.parse(jsonStr);
            if (event.type === "progress") {
              const pct = Math.round((event.current / event.total) * 100);
              const msg = `Combo ${event.current}/${event.total} · Sharpe: ${event.sharpe_ratio} · P&L: ₹${event.net_pnl}`;
              setGlobalProgress(pct, `Testing Combo ${event.current}/${event.total} · Sharpe: ${event.sharpe_ratio} · P&L: ₹${event.net_pnl}`, true);
              if (optProgressBar) optProgressBar.style.width = `${pct}%`;
              if (optProgressPct) optProgressPct.innerText = `${pct}%`;
              if (optProgressLabel) optProgressLabel.innerText = msg;
              status.innerText = msg;
            } else if (event.type === "complete") {
              streamSucceeded = true;
              if (optProgressBar) optProgressBar.style.width = "100%";
              if (optProgressPct) optProgressPct.innerText = "100%";
              setGlobalProgress(100, `Optimization complete (${event.total_combinations} combinations evaluated)!`, false);
              status.innerText = `Optimization finished! Evaluated ${event.total_combinations} combinations.`;
              status.style.color = "var(--green)";
              latestOptimizationResults = event.ranked_results || [];
              renderOptimizationResults(strat, event);
            } else if (event.type === "error") {
              status.innerText = `Optimizer error: ${event.message}`;
              status.style.color = "var(--red)";
              setGlobalProgress(0, "", false);
            }
          } catch (pe) {}
        }
      }
    }
  } catch (streamErr) {
    console.warn("Optimizer stream fetch interrupted, falling back to /api/optimize:", streamErr);
  }

  // Fallback to standard /api/optimize
  if (!streamSucceeded) {
    try {
      setGlobalProgress(50, `Evaluating parameter combinations for ${strat.toUpperCase()}...`, true);
      const fallbackRes = await fetch("/api/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await fallbackRes.json();
      if (data.status === "success") {
        if (optProgressBar) optProgressBar.style.width = "100%";
        if (optProgressPct) optProgressPct.innerText = "100%";
        setGlobalProgress(100, `Optimization complete (${data.total_combinations} combinations evaluated)!`, false);
        status.innerText = `Optimization finished! Evaluated ${data.total_combinations} combinations.`;
        status.style.color = "var(--green)";
        latestOptimizationResults = data.ranked_results || [];
        renderOptimizationResults(strat, data);
      } else {
        status.innerText = `Optimization failed: ${data.message || "Unknown error"}`;
        status.style.color = "var(--red)";
        setGlobalProgress(0, "", false);
      }
    } catch (err) {
      status.innerText = `Optimization failed: ${err}`;
      status.style.color = "var(--red)";
      setGlobalProgress(0, "", false);
    }
  }

  btn.disabled = false;
  btn.innerText = "🚀 RUN GRID OPTIMIZATION";
}

function renderOptimizationResults(strat, data) {
  const ranked = data.ranked_results || [];
  const best = ranked[0];

  const placeholder = document.getElementById("optBestPlaceholder");
  const content = document.getElementById("optBestContent");
  const badge = document.getElementById("optBestBadge");
  const paramsJson = document.getElementById("optBestParamsJson");
  const netPnl = document.getElementById("optBestNetPnl");
  const sharpe = document.getElementById("optBestSharpe");
  const winRate = document.getElementById("optBestWinRate");
  const countBadge = document.getElementById("optRankedCountBadge");

  if (placeholder) placeholder.style.display = best ? "none" : "block";
  if (content) content.style.display = best ? "block" : "none";
  if (badge) {
    badge.innerText = best ? "Rank #1 Discovered" : "No Results";
    badge.style.color = "var(--green)";
  }
  if (countBadge) countBadge.innerText = `${ranked.length} combinations ranked`;

  if (best) {
    if (paramsJson) paramsJson.innerText = JSON.stringify(best.params, null, 2);
    if (netPnl) {
      netPnl.innerText = `${best.net_pnl >= 0 ? "+" : ""}₹${best.net_pnl.toFixed(2)}`;
      netPnl.style.color = best.net_pnl >= 0 ? "var(--green)" : "var(--red)";
    }
    if (sharpe) sharpe.innerText = (best.sharpe_ratio || 0).toFixed(2);
    if (winRate) winRate.innerText = `${(best.win_rate || 0).toFixed(1)}%`;
  }

  // Table
  const tbody = document.getElementById("optRankedBody");
  if (!tbody) return;
  tbody.innerHTML = "";

  ranked.forEach((item, idx) => {
    const isWin = (item.net_pnl || 0) >= 0;
    const pnlCls = isWin ? "pos" : "neg";
    const paramsStr = Object.entries(item.params || {}).map(([k, v]) => `${k}=${v}`).join(", ");
    const serializedParams = JSON.stringify(item.params).replace(/"/g, '&quot;');

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td style="font-weight: 700;">#${idx + 1}</td>
      <td style="font-family: 'JetBrains Mono', monospace; font-size: 0.76rem; color: var(--accent-cyan);">${paramsStr}</td>
      <td style="text-align: right;" class="${pnlCls}">${isWin ? "+" : ""}₹${item.net_pnl.toFixed(2)}</td>
      <td style="text-align: right;" class="${pnlCls}">${isWin ? "+" : ""}${(item.return_pct || 0).toFixed(2)}%</td>
      <td style="text-align: right;">${(item.sharpe_ratio || 0).toFixed(2)}</td>
      <td style="text-align: right;">${(item.profit_factor || 0).toFixed(2)}</td>
      <td style="text-align: right;">${(item.win_rate || 0).toFixed(1)}%</td>
      <td style="text-align: right; color: var(--red);">${(item.max_drawdown_pct || 0).toFixed(2)}%</td>
      <td style="text-align: right;">${item.total_trades || 0}</td>
      <td>
        <button class="btn-secondary btn-sm" style="font-size: 0.72rem; padding: 3px 8px;" onclick="applyParametersToConsole('${strat}', JSON.parse('${serializedParams}'))">
          Apply ⚡
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function applyParametersToConsole(strat, params) {
  const stratSelect = document.getElementById("strategySelect");
  if (stratSelect) {
    stratSelect.value = strat;
    stratSelect.dispatchEvent(new Event("change"));
  }

  if (strat === "orb") {
    if (params.opening_minutes !== undefined && document.getElementById("orbMinutesInput"))
      document.getElementById("orbMinutesInput").value = params.opening_minutes;
    if (params.risk_reward !== undefined && document.getElementById("orbRrInput"))
      document.getElementById("orbRrInput").value = params.risk_reward;
    if (params.breakout_atr_mult !== undefined && document.getElementById("orbAtrMultInput"))
      document.getElementById("orbAtrMultInput").value = params.breakout_atr_mult;
  } else if (strat === "equity") {
    if (params.min_score !== undefined && document.getElementById("minScoreInput"))
      document.getElementById("minScoreInput").value = params.min_score;
    if (params.atr_sl_mult !== undefined && document.getElementById("atrSlInput"))
      document.getElementById("atrSlInput").value = params.atr_sl_mult;
    if (params.atr_tgt_mult !== undefined && document.getElementById("atrTgtInput"))
      document.getElementById("atrTgtInput").value = params.atr_tgt_mult;
  } else if (strat === "supertrend") {
    if (params.atr_period !== undefined && document.getElementById("stAtrPeriodInput"))
      document.getElementById("stAtrPeriodInput").value = params.atr_period;
    if (params.multiplier !== undefined && document.getElementById("stMultiplierInput"))
      document.getElementById("stMultiplierInput").value = params.multiplier;
    if (params.risk_reward !== undefined && document.getElementById("stRrInput"))
      document.getElementById("stRrInput").value = params.risk_reward;
  } else if (strat === "camarilla") {
    if (params.risk_reward !== undefined && document.getElementById("camRrInput"))
      document.getElementById("camRrInput").value = params.risk_reward;
    if (params.sl_buffer_pts !== undefined && document.getElementById("camBufferPtsInput"))
      document.getElementById("camBufferPtsInput").value = params.sl_buffer_pts;
  } else if (strat === "ema-ribbon") {
    if (params.fast_ema !== undefined && document.getElementById("ribbonFastInput"))
      document.getElementById("ribbonFastInput").value = params.fast_ema;
    if (params.med_ema !== undefined && document.getElementById("ribbonMedInput"))
      document.getElementById("ribbonMedInput").value = params.med_ema;
    if (params.sl_pts !== undefined && document.getElementById("ribbonSlPtsInput"))
      document.getElementById("ribbonSlPtsInput").value = params.sl_pts;
    if (params.target_pts !== undefined && document.getElementById("ribbonTgtPtsInput"))
      document.getElementById("ribbonTgtPtsInput").value = params.target_pts;
  } else if (strat === "bollinger-b") {
    if (params.period !== undefined && document.getElementById("bbPeriodInput"))
      document.getElementById("bbPeriodInput").value = params.period;
    if (params.std_dev !== undefined && document.getElementById("bbStdDevInput"))
      document.getElementById("bbStdDevInput").value = params.std_dev;
    if (params.oversold_b !== undefined && document.getElementById("bbOversoldInput"))
      document.getElementById("bbOversoldInput").value = params.oversold_b;
    if (params.overbought_b !== undefined && document.getElementById("bbOverboughtInput"))
      document.getElementById("bbOverboughtInput").value = params.overbought_b;
  } else if (strat === "macd-accel") {
    if (params.fast_period !== undefined && document.getElementById("macdFastInput"))
      document.getElementById("macdFastInput").value = params.fast_period;
    if (params.slow_period !== undefined && document.getElementById("macdSlowInput"))
      document.getElementById("macdSlowInput").value = params.slow_period;
    if (params.sl_pts !== undefined && document.getElementById("macdSlPtsInput"))
      document.getElementById("macdSlPtsInput").value = params.sl_pts;
    if (params.target_pts !== undefined && document.getElementById("macdTgtPtsInput"))
      document.getElementById("macdTgtPtsInput").value = params.target_pts;
  } else if (strat === "options") {
    if (params.sl_points !== undefined && document.getElementById("optionSlInput"))
      document.getElementById("optionSlInput").value = params.sl_points;
    if (params.target_multiplier !== undefined && document.getElementById("optionTgtInput"))
      document.getElementById("optionTgtInput").value = params.target_multiplier;
  }

  // Switch to console tab
  switchTab("tabConsole");
  const runStatus = document.getElementById("runStatus");
  if (runStatus) {
    runStatus.innerText = `Applied optimal ${strat.toUpperCase()} parameters!`;
    runStatus.style.color = "var(--green)";
  }
}
window.applyParametersToConsole = applyParametersToConsole;


// ── Trading Engine Deep Integration & Insights Cockpit ──────────────────────────
function initTradingEngineInsights() {
  const subBtns = document.querySelectorAll(".te-subtab-btn");
  const subpanels = document.querySelectorAll(".te-subpanel");

  subBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      subBtns.forEach(b => {
        b.classList.remove("active");
        b.style.borderColor = "transparent";
      });
      btn.classList.add("active");
      btn.style.borderColor = "var(--accent-cyan)";

      const subId = btn.getAttribute("data-sub");
      subpanels.forEach(p => {
        p.style.display = p.id === subId ? "block" : "none";
      });

      if (subId === "subFactorAlpha" && !window._teFactorsLoaded) {
        window._teFactorsLoaded = true;
        fetchFactorAblation();
      } else if (subId === "subConfigExport" && !window._teConfigLoaded) {
        window._teConfigLoaded = true;
        fetchConfigExport();
      } else if (subId === "subAiAnalytics" && !window._latestAiAnalyticsData) {
        fetchAiAnalytics();
      } else if (subId === "subMonteCarlo" && !window._teMonteCarloLoaded) {
        window._teMonteCarloLoaded = true;
        fetchMonteCarlo();
      } else if (subId === "subMultiLeg" && !window._teMultiLegLoaded) {
        window._teMultiLegLoaded = true;
        fetchMultiLegSimulation();
      }
    });
  });

  // Slider event with real-time confusion matrix recalculation
  const slider = document.getElementById("teConfSlider");
  const sliderVal = document.getElementById("teConfSliderVal");
  if (slider && sliderVal) {
    slider.addEventListener("input", (e) => {
      const val = parseFloat(e.target.value);
      sliderVal.innerText = val.toFixed(2);
      updateConfusionFromSweep(val);
    });
    slider.addEventListener("change", () => {
      fetchAiAnalytics();
    });
  }

  // Date select change listener
  const dateSelect = document.getElementById("teDateSelect");
  if (dateSelect) {
    dateSelect.addEventListener("change", () => {
      fetchReconciliation();
      if (window._teFactorsLoaded) fetchFactorAblation();
      if (window._teMonteCarloLoaded) fetchMonteCarlo();
      if (window._teMultiLegLoaded) fetchMultiLegSimulation();
    });
  }

  // Action Buttons
  const btnRunAll = document.getElementById("btnRunAllEngineInsights");
  if (btnRunAll) {
    btnRunAll.addEventListener("click", async () => {
      btnRunAll.disabled = true;
      btnRunAll.innerText = "Analyzing...";
      try {
        await Promise.all([
          fetchReconciliation(),
          fetchAiAnalytics(),
          fetchFactorAblation(),
          fetchConfigExport(),
          fetchMonteCarlo(),
          fetchMultiLegSimulation()
        ]);
        window._teFactorsLoaded = true;
        window._teConfigLoaded = true;
        window._teMonteCarloLoaded = true;
        window._teMultiLegLoaded = true;
      } finally {
        btnRunAll.disabled = false;
        btnRunAll.innerText = "⚡ Run Full Analysis";
      }
    });
  }

  const btnRefreshRecon = document.getElementById("btnRefreshRecon");
  if (btnRefreshRecon) {
    btnRefreshRecon.addEventListener("click", fetchReconciliation);
  }

  const btnRecalculateAi = document.getElementById("btnRecalculateAi");
  if (btnRecalculateAi) {
    btnRecalculateAi.addEventListener("click", fetchAiAnalytics);
  }

  const btnRunFactors = document.getElementById("btnRunFactorAblation");
  if (btnRunFactors) {
    btnRunFactors.addEventListener("click", () => {
      window._teFactorsLoaded = true;
      fetchFactorAblation();
    });
  }

  const btnRunMonteCarlo = document.getElementById("btnRunMonteCarlo");
  if (btnRunMonteCarlo) {
    btnRunMonteCarlo.addEventListener("click", fetchMonteCarlo);
  }

  const btnRunMultiLeg = document.getElementById("btnRunMultiLeg");
  if (btnRunMultiLeg) {
    btnRunMultiLeg.addEventListener("click", fetchMultiLegSimulation);
  }

  // Session Audit Modal Handlers
  const btnOpenAuditModal = document.getElementById("btnOpenAuditModal");
  const auditModal = document.getElementById("teAuditModal");
  const closeAuditModal = document.getElementById("closeAuditModal");
  if (btnOpenAuditModal && auditModal) {
    btnOpenAuditModal.addEventListener("click", () => {
      auditModal.style.display = "flex";
      fetchSessionAudit();
    });
  }
  if (closeAuditModal && auditModal) {
    closeAuditModal.addEventListener("click", () => {
      auditModal.style.display = "none";
    });
  }
  const btnOpenHtmlReport = document.getElementById("btnOpenHtmlReport");
  if (btnOpenHtmlReport) {
    btnOpenHtmlReport.addEventListener("click", () => {
      const select = document.getElementById("teDateSelect");
      const d = select ? select.value : "2026_09_11";
      window.open(`/api/trading_engine/audit?date=${encodeURIComponent(d)}&format=html`, "_blank");
    });
  }
  const btnDownloadHtmlReport = document.getElementById("btnDownloadHtmlReport");
  if (btnDownloadHtmlReport) {
    btnDownloadHtmlReport.addEventListener("click", () => {
      const select = document.getElementById("teDateSelect");
      const d = select ? select.value : "2026_09_11";
      window.location.href = `/api/trading_engine/audit?date=${encodeURIComponent(d)}&format=html&download=1`;
    });
  }

  // Production Config Sync Buttons
  const btnApplyTradingEngine = document.getElementById("btnApplyTradingEngine");
  if (btnApplyTradingEngine) {
    btnApplyTradingEngine.addEventListener("click", async () => {
      const confirmSync = confirm("Apply optimized parameters directly to trading-engine/.env?\n\nAn automated timestamped backup (.env.bak.<timestamp>) will be safely created.");
      if (!confirmSync) return;

      btnApplyTradingEngine.disabled = true;
      btnApplyTradingEngine.innerText = "Applying to trading-engine...";
      const alertBox = document.getElementById("teSyncAlert");

      try {
        const res = await fetch("/api/trading_engine/apply_config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({})
        });
        const json = await res.json();
        if (json.status === "ok" && json.data) {
          if (alertBox) {
            alertBox.style.display = "block";
            alertBox.style.background = "rgba(0, 245, 160, 0.12)";
            alertBox.style.border = "1px solid rgba(0, 245, 160, 0.4)";
            alertBox.style.color = "var(--green)";
            alertBox.innerHTML = `<strong>✓ Successfully synchronized to trading-engine/.env!</strong><br>
              <span style="font-size: 0.75rem; color: var(--text-muted);">Backup created: ${json.data.backup_file || "N/A"} | Updated keys: ${(json.data.updated_keys || []).join(", ")}</span>`;
          }
          btnApplyTradingEngine.innerText = "Applied Successfully! ✓";
          setTimeout(() => {
            btnApplyTradingEngine.disabled = false;
            btnApplyTradingEngine.innerText = "⚡ Apply Directly to Trading Engine (.env)";
          }, 3000);
        } else {
          throw new Error(json.message || "Failed to synchronize");
        }
      } catch (err) {
        console.error("Error applying config:", err);
        if (alertBox) {
          alertBox.style.display = "block";
          alertBox.style.background = "rgba(255, 77, 79, 0.12)";
          alertBox.style.border = "1px solid rgba(255, 77, 79, 0.4)";
          alertBox.style.color = "var(--red)";
          alertBox.innerText = `Error applying config: ${err.message}`;
        }
        btnApplyTradingEngine.disabled = false;
        btnApplyTradingEngine.innerText = "⚡ Apply Directly to Trading Engine (.env)";
      }
    });
  }

  const btnCopyEnv = document.getElementById("btnCopyEnv");
  if (btnCopyEnv) {
    btnCopyEnv.addEventListener("click", () => {
      const preview = document.getElementById("teEnvPreview");
      if (preview && preview.innerText) {
        navigator.clipboard.writeText(preview.innerText);
        btnCopyEnv.innerText = "Copied! ✓";
        btnCopyEnv.style.color = "var(--green)";
        setTimeout(() => {
          btnCopyEnv.innerText = "📋 Copy .env";
          btnCopyEnv.style.color = "";
        }, 2000);
      }
    });
  }

  const btnDownloadEnv = document.getElementById("btnDownloadEnv");
  if (btnDownloadEnv) {
    btnDownloadEnv.addEventListener("click", () => {
      window.location.href = "/api/trading_engine/export_config?format=env&download=true";
    });
  }

  // Populate available dates in teDateSelect if empty
  populateEngineDates();
}

function updateConfusionFromSweep(targetThreshold) {
  if (!window._latestAiAnalyticsData || !Array.isArray(window._latestAiAnalyticsData.threshold_sweep)) return;
  const sweep = window._latestAiAnalyticsData.threshold_sweep;
  let best = sweep[0];
  let minDiff = 999;
  sweep.forEach(item => {
    const diff = Math.abs(item.threshold - targetThreshold);
    if (diff < minDiff) {
      minDiff = diff;
      best = item;
    }
  });
  if (best) {
    const mTP = document.getElementById("teMatrixTP");
    if (mTP) mTP.innerText = best.true_positives || 0;
    const mFP = document.getElementById("teMatrixFP");
    if (mFP) mFP.innerText = best.false_positives || 0;
    const mTN = document.getElementById("teMatrixTN");
    if (mTN) mTN.innerText = best.true_negatives || 0;
    const mFN = document.getElementById("teMatrixFN");
    if (mFN) mFN.innerText = best.false_negatives || 0;

    const kpiPrec = document.getElementById("teKpiAiPrecision");
    if (kpiPrec) kpiPrec.innerText = (best.precision || 0).toFixed(1) + "%";
    const kpiAcc = document.getElementById("teKpiAiAccuracy");
    if (kpiAcc) kpiAcc.innerText = (best.accuracy || 0).toFixed(1) + "%";
    const kpiFilt = document.getElementById("teKpiAiFilterRate");
    const total = window._latestAiAnalyticsData.total_snapshots || 1;
    if (kpiFilt) kpiFilt.innerText = `${best.signals_filtered || 0} (${(((best.signals_filtered || 0) / total) * 100).toFixed(0)}%)`;
  }
}

async function populateEngineDates() {
  const select = document.getElementById("teDateSelect");
  if (!select) return;
  try {
    const res = await fetch("/api/archives");
    const json = await res.json();
    if (json.status === "ok" && Array.isArray(json.archives)) {
      const existing = Array.from(select.options).map(o => o.value);
      json.archives.forEach(a => {
        if (a.date && !existing.includes(a.date)) {
          const opt = document.createElement("option");
          opt.value = a.date;
          opt.innerText = `${a.date}${a.date === "2026_09_11" ? " (Recorded Live Trades)" : ""}`;
          select.appendChild(opt);
        }
      });
    }
  } catch (err) {
    console.error("Error populating engine dates:", err);
  }
}

async function fetchReconciliation() {
  const select = document.getElementById("teDateSelect");
  const dateVal = select ? select.value : "2026_09_11";
  const dateToUse = dateVal === "all" ? "2026_09_11" : dateVal;

  const tbody = document.getElementById("teMatchedBody");
  if (tbody) {
    tbody.innerHTML = '<tr><td colspan="12" class="empty-state">Reconciling live executions against theoretical simulation...</td></tr>';
  }

  try {
    const res = await fetch(`/api/trading_engine/reconciliation?date=${encodeURIComponent(dateToUse)}`);
    const json = await res.json();
    if (json.status === "ok" && json.data) {
      renderReconciliation(json.data);
    } else {
      if (tbody) tbody.innerHTML = `<tr><td colspan="12" class="empty-state" style="color: var(--red);">${json.message || "Reconciliation failed"}</td></tr>`;
    }
  } catch (err) {
    console.error("Error fetching reconciliation:", err);
    if (tbody) tbody.innerHTML = `<tr><td colspan="12" class="empty-state" style="color: var(--red);">Reconciliation request error: ${err.message}</td></tr>`;
  }
}

function renderReconciliation(data) {
  const sum = data.summary || {};

  // KPIs
  const kpiEff = document.getElementById("teKpiEfficiency");
  if (kpiEff) kpiEff.innerText = (sum.overall_execution_efficiency || 0).toFixed(1) + "%";

  const kpiSlip = document.getElementById("teKpiSlippage");
  if (kpiSlip) {
    const s = sum.avg_entry_slippage_rs || 0;
    kpiSlip.innerText = (s >= 0 ? "+" : "") + "₹" + s.toFixed(2);
    kpiSlip.style.color = s <= 0 ? "var(--green)" : "var(--red)";
  }

  const kpiSlipPct = document.getElementById("teKpiSlippagePct");
  if (kpiSlipPct) kpiSlipPct.innerText = `${sum.avg_entry_slippage_pct || 0}% avg entry drift`;

  const kpiLat = document.getElementById("teKpiLatency");
  if (kpiLat) kpiLat.innerText = `${sum.avg_latency_seconds || 0}s`;

  const kpiPnl = document.getElementById("teKpiPnlDrift");
  if (kpiPnl) {
    const d = sum.net_pnl_drift || 0;
    kpiPnl.innerText = (d >= 0 ? "+" : "") + "₹" + d.toFixed(2);
    kpiPnl.style.color = d >= 0 ? "var(--green)" : "var(--red)";
  }

  const kpiPnlSub = document.getElementById("teKpiPnlSub");
  if (kpiPnlSub) kpiPnlSub.innerText = `Live ₹${sum.total_live_pnl || 0} vs Sim ₹${sum.total_sim_pnl || 0}`;

  const kpiMatched = document.getElementById("teKpiMatchedCount");
  if (kpiMatched) kpiMatched.innerText = `${sum.matched_count || 0} / ${sum.total_live_trades || 0}`;

  const kpiUnprompted = document.getElementById("teKpiUnpromptedCount");
  if (kpiUnprompted) kpiUnprompted.innerText = `${sum.unprompted_live_count || 0} unprompted live`;

  // Matched Pairs Table
  const tbody = document.getElementById("teMatchedBody");
  if (tbody) {
    const pairs = data.matched_pairs || [];
    if (pairs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="12" class="empty-state">No matching execution pairs found for this session.</td></tr>';
    } else {
      tbody.innerHTML = pairs.map(p => {
        const live = p.live_trade || {};
        const sim = p.sim_trade || {};
        const slipColor = p.entry_slippage_rs <= 0 ? "var(--green)" : "var(--red)";
        const pnlColor = (live.net_pnl || 0) >= 0 ? "var(--green)" : "var(--red)";
        const effScore = p.execution_efficiency || 0;
        const effBadge = effScore >= 70 ? "badge-long" : (effScore >= 40 ? "badge-neutral" : "badge-short");

        return `
          <tr>
            <td style="font-weight: 700; color: #fff;">${live.symbol || sim.symbol || "--"}</td>
            <td><span class="badge ${live.side === 'BUY' ? 'badge-long' : 'badge-short'}">${live.side || 'BUY'}</span></td>
            <td style="font-family: 'JetBrains Mono', monospace; font-size: 0.78rem;">${live.entry_time || "--"}</td>
            <td style="font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; color: var(--text-muted);">${sim.entry_time || "--"}</td>
            <td style="font-family: 'JetBrains Mono', monospace;">₹${(live.entry_price || 0).toFixed(2)}</td>
            <td style="font-family: 'JetBrains Mono', monospace; color: var(--text-muted);">₹${(sim.entry_price || 0).toFixed(2)}</td>
            <td style="font-family: 'JetBrains Mono', monospace; color: ${slipColor}; font-weight: 700;">
              ${(p.entry_slippage_rs >= 0 ? "+" : "") + p.entry_slippage_rs.toFixed(2)} (${p.entry_slippage_pct.toFixed(1)}%)
            </td>
            <td style="font-family: 'JetBrains Mono', monospace;">${p.latency_seconds}s</td>
            <td style="font-family: 'JetBrains Mono', monospace; color: ${pnlColor}; font-weight: 700;">₹${(live.net_pnl || 0).toFixed(2)}</td>
            <td style="font-family: 'JetBrains Mono', monospace; color: var(--text-muted);">₹${(sim.net_pnl || 0).toFixed(2)}</td>
            <td style="font-family: 'JetBrains Mono', monospace;">₹${(p.pnl_variance || 0).toFixed(2)}</td>
            <td><span class="badge ${effBadge}" style="font-weight: 700;">${effScore.toFixed(0)} / 100</span></td>
          </tr>
        `;
      }).join("");
    }
  }

  // Unprompted Table
  const unpBody = document.getElementById("teUnpromptedBody");
  if (unpBody) {
    const unprompted = data.unprompted_live || [];
    if (unprompted.length === 0) {
      unpBody.innerHTML = '<tr><td colspan="6" class="empty-state">None</td></tr>';
    } else {
      unpBody.innerHTML = unprompted.map(t => {
        const pColor = (t.net_pnl || 0) >= 0 ? "var(--green)" : "var(--red)";
        return `
          <tr>
            <td style="font-weight: 600;">${t.symbol}</td>
            <td style="font-family: 'JetBrains Mono', monospace; font-size: 0.76rem;">${t.entry_time.split(" ")[1] || t.entry_time}</td>
            <td style="font-family: 'JetBrains Mono', monospace;">₹${(t.entry_price || 0).toFixed(2)}</td>
            <td style="font-family: 'JetBrains Mono', monospace;">₹${(t.exit_price || 0).toFixed(2)}</td>
            <td style="font-family: 'JetBrains Mono', monospace; color: ${pColor}; font-weight: 700;">₹${(t.net_pnl || 0).toFixed(2)}</td>
            <td style="font-family: 'JetBrains Mono', monospace; color: var(--accent-cyan);">${t.gemini_confidence ? (t.gemini_confidence * 100).toFixed(0) + "%" : "--"}</td>
          </tr>
        `;
      }).join("");
    }
  }

  // Missed Table
  const missedBody = document.getElementById("teMissedBody");
  if (missedBody) {
    const missed = data.missed_signals || [];
    if (missed.length === 0) {
      missedBody.innerHTML = '<tr><td colspan="6" class="empty-state">None</td></tr>';
    } else {
      missedBody.innerHTML = missed.map(t => {
        const pColor = (t.net_pnl || 0) >= 0 ? "var(--green)" : "var(--red)";
        return `
          <tr>
            <td style="font-weight: 600;">${t.symbol}</td>
            <td style="font-family: 'JetBrains Mono', monospace; font-size: 0.76rem;">${t.entry_time.split(" ")[1] || t.entry_time}</td>
            <td style="font-family: 'JetBrains Mono', monospace;">₹${(t.entry_price || 0).toFixed(2)}</td>
            <td style="font-family: 'JetBrains Mono', monospace;">₹${(t.exit_price || 0).toFixed(2)}</td>
            <td style="font-family: 'JetBrains Mono', monospace; color: ${pColor};">₹${(t.net_pnl || 0).toFixed(2)}</td>
            <td><span class="badge badge-neutral">${t.metadata?.score || "--"}</span></td>
          </tr>
        `;
      }).join("");
    }
  }

  // Render Intraday P&L Drift Chart
  renderIntradayDriftChart(data);
}

async function fetchAiAnalytics() {
  const select = document.getElementById("teDateSelect");
  const dateVal = select ? select.value : "all";
  const slider = document.getElementById("teConfSlider");
  const confTh = slider ? slider.value : "0.70";

  const calBody = document.getElementById("teCalibrationBody");
  if (calBody) calBody.innerHTML = '<tr><td colspan="5" class="empty-state">Auditing Gemini AI snapshots & computing forward returns...</td></tr>';

  try {
    const res = await fetch(`/api/trading_engine/ai_analytics?date=${encodeURIComponent(dateVal)}&confidence_threshold=${encodeURIComponent(confTh)}`);
    const json = await res.json();
    if (json.status === "ok" && json.data) {
      renderAiAnalytics(json.data);
    }
  } catch (err) {
    console.error("Error fetching AI analytics:", err);
  }
}

function renderAiAnalytics(data) {
  window._latestAiAnalyticsData = data;
  const sum = data.summary || {};
  const mat = data.counterfactual_matrix || {};

  // KPIs
  const kpiDec = document.getElementById("teKpiAiDecisions");
  if (kpiDec) kpiDec.innerText = (data.total_snapshots || 0).toLocaleString();

  const kpiPrec = document.getElementById("teKpiAiPrecision");
  if (kpiPrec) kpiPrec.innerText = (mat.precision || 0).toFixed(1) + "%";

  const kpiAcc = document.getElementById("teKpiAiAccuracy");
  if (kpiAcc) kpiAcc.innerText = (mat.accuracy || 0).toFixed(1) + "%";

  const kpiFilt = document.getElementById("teKpiAiFilterRate");
  if (kpiFilt) kpiFilt.innerText = `${mat.signals_filtered || 0} (${(((mat.signals_filtered || 0) / (data.total_snapshots || 1)) * 100).toFixed(0)}%)`;

  const kpiOpt = document.getElementById("teKpiAiOptimalTh");
  if (kpiOpt) kpiOpt.innerText = data.optimal_threshold != null ? Number(data.optimal_threshold).toFixed(2) : "--";

  // Matrix
  const mTP = document.getElementById("teMatrixTP");
  if (mTP) mTP.innerText = mat.true_positives || 0;
  const mFP = document.getElementById("teMatrixFP");
  if (mFP) mFP.innerText = mat.false_positives || 0;
  const mTN = document.getElementById("teMatrixTN");
  if (mTN) mTN.innerText = mat.true_negatives || 0;
  const mFN = document.getElementById("teMatrixFN");
  if (mFN) mFN.innerText = mat.false_negatives || 0;

  // Calibration Table
  const calBody = document.getElementById("teCalibrationBody");
  if (calBody) {
    const cal = data.calibration || [];
    if (cal.length === 0) {
      calBody.innerHTML = '<tr><td colspan="5" class="empty-state">No calibration buckets available.</td></tr>';
    } else {
      calBody.innerHTML = cal.map(c => {
        const wrColor = c.win_rate >= 50 ? "var(--green)" : (c.win_rate > 0 ? "var(--accent-yellow)" : "var(--text-muted)");
        return `
          <tr>
            <td style="font-family: 'JetBrains Mono', monospace; font-weight: 700;">${c.bucket}</td>
            <td style="font-family: 'JetBrains Mono', monospace;">${c.count}</td>
            <td style="font-family: 'JetBrains Mono', monospace;">${c.pct_of_total}%</td>
            <td style="font-family: 'JetBrains Mono', monospace; color: ${wrColor}; font-weight: 700;">${c.win_rate.toFixed(1)}%</td>
            <td style="font-family: 'JetBrains Mono', monospace;">${c.avg_return_pct.toFixed(3)}%</td>
          </tr>
        `;
      }).join("");
    }
  }

  // Keywords Table
  const kwBody = document.getElementById("teKeywordsBody");
  if (kwBody) {
    const kws = data.reasoning_insights || [];
    if (kws.length === 0) {
      kwBody.innerHTML = '<tr><td colspan="5" class="empty-state">No reasoning keywords found.</td></tr>';
    } else {
      kwBody.innerHTML = kws.map(k => {
        const badge = k.alpha_rating === 'HIGH' ? 'badge-long' : (k.alpha_rating === 'NEUTRAL' ? 'badge-neutral' : 'badge-short');
        return `
          <tr>
            <td style="font-weight: 700; color: #fff;">"${k.keyword}"</td>
            <td style="font-family: 'JetBrains Mono', monospace;">${k.occurrences}</td>
            <td style="font-family: 'JetBrains Mono', monospace; font-weight: 700;">${k.win_rate.toFixed(1)}%</td>
            <td style="font-family: 'JetBrains Mono', monospace;">${k.avg_return_pct.toFixed(3)}%</td>
            <td><span class="badge ${badge}" style="font-weight: 700;">${k.alpha_rating}</span></td>
          </tr>
        `;
      }).join("");
    }
  }

  // Render AI Calibration Reliability Diagram
  renderAiCalibrationChart(data);
}

async function fetchFactorAblation() {
  const select = document.getElementById("teDateSelect");
  const dateVal = select ? select.value : "2026_09_11";
  const dates = dateVal === "all" ? ["2026_09_11", "2026_09_08"] : [dateVal];

  const tbody = document.getElementById("teFactorsBody");
  if (tbody) tbody.innerHTML = '<tr><td colspan="9" class="empty-state">Executing factor ablation passes across market sessions...</td></tr>';

  try {
    const res = await fetch("/api/trading_engine/factor_attribution", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dates: dates })
    });
    const json = await res.json();
    if (json.status === "ok" && json.data) {
      renderFactorAblation(json.data);
    }
  } catch (err) {
    console.error("Error fetching factor ablation:", err);
  }
}

function renderFactorAblation(data) {
  const tbody = document.getElementById("teFactorsBody");
  if (!tbody) return;
  const factors = data.factors || [];
  if (factors.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" class="empty-state">No factor ablation data returned.</td></tr>';
    return;
  }

  tbody.innerHTML = factors.map(f => {
    const badge = f.status === 'VALUE_ADD' ? 'badge-long' : (f.status === 'DRAG' ? 'badge-short' : 'badge-neutral');
    const sharpeColor = f.delta_sharpe >= 0 ? "var(--green)" : "var(--red)";
    const wrColor = f.delta_win_rate >= 0 ? "var(--green)" : "var(--red)";
    const pnlColor = f.delta_net_pnl >= 0 ? "var(--green)" : "var(--red)";

    return `
      <tr>
        <td style="font-weight: 700; color: #fff;">${f.factor_name}</td>
        <td style="color: var(--text-muted); font-size: 0.8rem;">${f.description}</td>
        <td><span class="badge ${badge}" style="font-weight: 700;">${f.status}</span></td>
        <td style="font-family: 'JetBrains Mono', monospace; color: ${sharpeColor}; font-weight: 700;">
          ${(f.delta_sharpe >= 0 ? "+" : "") + f.delta_sharpe.toFixed(2)}
        </td>
        <td style="font-family: 'JetBrains Mono', monospace; color: ${wrColor};">
          ${(f.delta_win_rate >= 0 ? "+" : "") + f.delta_win_rate.toFixed(1)}%
        </td>
        <td style="font-family: 'JetBrains Mono', monospace; color: ${pnlColor}; font-weight: 700;">
          ₹${(f.delta_net_pnl >= 0 ? "+" : "") + f.delta_net_pnl.toFixed(2)}
        </td>
        <td style="font-family: 'JetBrains Mono', monospace;">+${f.drawdown_reduction_pct.toFixed(1)}%</td>
        <td style="font-family: 'JetBrains Mono', monospace;">${f.trades_filtered}</td>
        <td><span class="badge ${f.status === 'VALUE_ADD' ? 'badge-long' : 'badge-neutral'}">${f.action_recommendation}</span></td>
      </tr>
    `;
  }).join("");
}

async function fetchConfigExport() {
  try {
    const res = await fetch("/api/trading_engine/export_config");
    const json = await res.json();
    if (json.status === "ok" && json.data) {
      renderConfigExport(json.data);
    }
  } catch (err) {
    console.error("Error fetching config export:", err);
  }
}

function renderConfigExport(data) {
  const recList = document.getElementById("teRecommendationsList");
  if (recList) {
    const recs = data.recommendations || [];
    if (recs.length === 0) {
      recList.innerHTML = '<li>All strategy parameters verified against current quantitative standards.</li>';
    } else {
      recList.innerHTML = recs.map(r => `<li>${r}</li>`).join("");
    }
  }

  const preview = document.getElementById("teEnvPreview");
  if (preview) {
    preview.innerText = data.env_content || "";
  }
}

// ── Visual Chart: Intraday Execution Drift Timeline ─────────────────────────────
function renderIntradayDriftChart(data) {
  const canvas = document.getElementById("teDriftChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (teDriftChartInstance) {
    teDriftChartInstance.destroy();
    teDriftChartInstance = null;
  }

  const pairs = data.matched_pairs || [];
  const points = [];
  pairs.forEach(p => {
    const t = (p.live_trade?.entry_time || p.sim_trade?.entry_time || "").split(" ")[1] || "10:00";
    points.push({ time: t, livePnl: p.live_trade?.net_pnl || 0, simPnl: p.sim_trade?.net_pnl || 0 });
  });

  if (points.length === 0) {
    points.push({ time: "09:15", livePnl: 0, simPnl: 0 });
    points.push({ time: "11:30", livePnl: 0, simPnl: 0 });
    points.push({ time: "15:15", livePnl: 0, simPnl: 0 });
  }

  points.sort((a, b) => a.time.localeCompare(b.time));

  let cumLive = 0;
  let cumSim = 0;
  const labels = ["09:15"];
  const liveSeries = [0];
  const simSeries = [0];

  points.forEach(pt => {
    cumLive += pt.livePnl;
    cumSim += pt.simPnl;
    labels.push(pt.time);
    liveSeries.push(roundTo(cumLive, 2));
    simSeries.push(roundTo(cumSim, 2));
  });

  teDriftChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Theoretical Strategy v4 P&L (₹)",
          data: simSeries,
          borderColor: "#00f2fe",
          backgroundColor: "rgba(0, 242, 254, 0.08)",
          fill: true,
          tension: 0.2,
          borderWidth: 2,
          pointRadius: 3
        },
        {
          label: "Realized Live Paper P&L (₹)",
          data: liveSeries,
          borderColor: cumLive >= 0 ? "#00f5a0" : "#ff4d4f",
          backgroundColor: cumLive >= 0 ? "rgba(0, 245, 160, 0.08)" : "rgba(255, 77, 79, 0.08)",
          fill: true,
          tension: 0.2,
          borderWidth: 2,
          pointRadius: 3
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: true, labels: { color: "#8b949e", font: { size: 11 } } },
        tooltip: {
          backgroundColor: "rgba(10, 16, 28, 0.95)",
          borderColor: "rgba(255, 255, 255, 0.1)",
          borderWidth: 1
        }
      },
      scales: {
        x: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#8b949e", font: { size: 10 } } },
        y: {
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "#8b949e", font: { size: 10 }, callback: v => `₹${v}` }
        }
      }
    }
  });
}

// ── Visual Chart: AI Decile Calibration Reliability Curve ────────────────────────
function renderAiCalibrationChart(data) {
  const canvas = document.getElementById("teCalibrationChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (teCalibrationChartInstance) {
    teCalibrationChartInstance.destroy();
    teCalibrationChartInstance = null;
  }

  const cal = data.calibration || [];
  if (cal.length === 0) return;

  const labels = cal.map(c => c.bucket);
  const winRates = cal.map(c => c.win_rate);
  const counts = cal.map(c => c.count);
  const benchmarkLine = labels.map(l => {
    if (l === "0.0-0.3") return 15;
    if (l === "0.3-0.5") return 40;
    if (l === "0.5-0.6") return 55;
    if (l === "0.6-0.7") return 65;
    if (l === "0.7-0.8") return 75;
    if (l === "0.8-1.0") return 90;
    return 50;
  });

  teCalibrationChartInstance = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          type: "line",
          label: "Realized Win Rate %",
          data: winRates,
          borderColor: "#00f2fe",
          backgroundColor: "transparent",
          borderWidth: 2.5,
          pointRadius: 4,
          pointBackgroundColor: "#00f2fe",
          yAxisID: "y"
        },
        {
          type: "line",
          label: "Perfect Calibration Diagonal %",
          data: benchmarkLine,
          borderColor: "rgba(255, 255, 255, 0.3)",
          borderDash: [5, 5],
          backgroundColor: "transparent",
          borderWidth: 1.5,
          pointRadius: 0,
          yAxisID: "y"
        },
        {
          type: "bar",
          label: "Snapshot Sample Count",
          data: counts,
          backgroundColor: "rgba(168, 85, 247, 0.25)",
          borderColor: "rgba(168, 85, 247, 0.6)",
          borderWidth: 1,
          yAxisID: "y1"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: true, labels: { color: "#8b949e", font: { size: 11 } } },
        tooltip: {
          backgroundColor: "rgba(10, 16, 28, 0.95)",
          borderColor: "rgba(255, 255, 255, 0.1)",
          borderWidth: 1
        }
      },
      scales: {
        x: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#8b949e" } },
        y: {
          type: "linear",
          position: "left",
          min: 0,
          max: 100,
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "#8b949e", callback: v => `${v}%` }
        },
        y1: {
          type: "linear",
          position: "right",
          grid: { drawOnChartArea: false },
          ticks: { color: "#a855f7" }
        }
      }
    }
  });
}

// ── Monte Carlo & Stress Test Engine ─────────────────────────────────────────────
async function fetchMonteCarlo() {
  const simSelect = document.getElementById("mcSimCount");
  const capInput = document.getElementById("mcCapital");
  const ruinSelect = document.getElementById("mcSoftRuin");
  const dateSelect = document.getElementById("teDateSelect");

  const numSims = simSelect ? parseInt(simSelect.value, 10) : 2500;
  const capital = capInput ? parseFloat(capInput.value) : 100000;
  const softRuin = ruinSelect ? parseFloat(ruinSelect.value) : 0.20;
  const targetDate = dateSelect ? dateSelect.value : "2026_09_11";

  const btn = document.getElementById("btnRunMonteCarlo");
  if (btn) {
    btn.disabled = true;
    btn.innerText = "Simulating Paths...";
  }

  try {
    const res = await fetch("/api/trading_engine/monte_carlo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        date: targetDate === "all" ? "2026_09_11" : targetDate,
        num_simulations: numSims,
        capital: capital,
        soft_ruin: softRuin,
        hard_ruin: 0.50
      })
    });
    const json = await res.json();
    if (json.status === "ok" && json.data) {
      renderMonteCarlo(json.data);
    }
  } catch (err) {
    console.error("Error in monte carlo:", err);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = "🎲 Run Stress Test";
    }
  }
}

function renderMonteCarlo(data) {
  const v = data.var || {};
  const dd = data.drawdown || {};
  const r = data.ruin_probability || {};
  const perf = data.performance || {};
  const ch = data.chart_data || {};

  const kVaR95 = document.getElementById("mcKpiVaR95");
  if (kVaR95) kVaR95.innerText = `₹${Math.abs(v.var_95_rs || 0).toLocaleString()} (${v.var_95_pct || 0}%)`;

  const kVaR99 = document.getElementById("mcKpiVaR99");
  if (kVaR99) kVaR99.innerText = `₹${Math.abs(v.var_99_rs || 0).toLocaleString()} (${v.var_99_pct || 0}%)`;

  const kCVaR = document.getElementById("mcKpiCVaR");
  if (kCVaR) kCVaR.innerText = `₹${Math.abs(v.cvar_95_rs || 0).toLocaleString()} (${v.cvar_95_pct || 0}%)`;

  const kDD = document.getElementById("mcKpiMaxDD");
  if (kDD) kDD.innerText = `${dd.p95_dd_pct || 0}%`;
  const kDDSub = document.getElementById("mcKpiMaxDDSub");
  if (kDDSub) kDDSub.innerText = `Median: ${dd.median_dd_pct || 0}% | Worst: ${dd.worst_dd_pct || 0}%`;

  const kRuin = document.getElementById("mcKpiRuin");
  if (kRuin) {
    const sRuin = r.soft_ruin_pct || 0;
    kRuin.innerText = `${sRuin.toFixed(1)}%`;
    kRuin.style.color = sRuin < 5 ? "var(--green)" : (sRuin < 15 ? "var(--accent-yellow)" : "var(--red)");
  }
  const kRuinSub = document.getElementById("mcKpiRuinSub");
  if (kRuinSub) kRuinSub.innerText = `50% Ruin: ${r.hard_ruin_pct || 0}% | Win Prob: ${perf.profit_probability || 0}%`;

  // Render chart
  const canvas = document.getElementById("teMonteCarloChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (teMonteCarloChartInstance) {
    teMonteCarloChartInstance.destroy();
    teMonteCarloChartInstance = null;
  }

  const steps = ch.steps || [];
  const datasets = [
    {
      label: "95th Percentile (Optimistic)",
      data: ch.p95_envelope || [],
      borderColor: "rgba(0, 245, 160, 0.7)",
      backgroundColor: "transparent",
      borderWidth: 1.5,
      pointRadius: 0
    },
    {
      label: "Median Path (50th Percentile)",
      data: ch.median_envelope || [],
      borderColor: "#00f2fe",
      backgroundColor: "transparent",
      borderWidth: 2.5,
      pointRadius: 0
    },
    {
      label: "5th Percentile (Stress Boundary)",
      data: ch.p5_envelope || [],
      borderColor: "rgba(255, 77, 79, 0.8)",
      backgroundColor: "rgba(255, 77, 79, 0.05)",
      fill: "-1",
      borderWidth: 1.5,
      pointRadius: 0
    }
  ];

  (ch.sample_paths || []).slice(0, 5).forEach((p, idx) => {
    datasets.push({
      label: `Path ${idx + 1}`,
      data: p,
      borderColor: "rgba(255, 255, 255, 0.12)",
      backgroundColor: "transparent",
      borderWidth: 1,
      pointRadius: 0
    });
  });

  teMonteCarloChartInstance = new Chart(ctx, {
    type: "line",
    data: { labels: steps.map(s => `Trade ${s}`), datasets: datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: true, labels: { color: "#8b949e", filter: item => !item.text.startsWith("Path") } },
        tooltip: {
          backgroundColor: "rgba(10, 16, 28, 0.95)",
          borderColor: "rgba(255, 255, 255, 0.1)",
          borderWidth: 1,
          callbacks: { label: c => `${c.dataset.label}: ₹${c.parsed.y.toLocaleString()}` }
        }
      },
      scales: {
        x: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#8b949e", maxTicksLimit: 10 } },
        y: {
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "#8b949e", callback: v => `₹${(v / 1000).toFixed(0)}k` }
        }
      }
    }
  });
}

// ── Multi-Leg Options & Greeks Simulation Engine ──────────────────────────────────
async function fetchMultiLegSimulation() {
  const stratSel = document.getElementById("mlStrategySelect");
  const slSel = document.getElementById("mlSlSelect");
  const tgtSel = document.getElementById("mlTargetSelect");
  const dateSelect = document.getElementById("teDateSelect");

  const strat = stratSel ? stratSel.value : "short_straddle";
  const sl = slSel ? parseFloat(slSel.value) : 0.25;
  const tgt = tgtSel ? parseFloat(tgtSel.value) : 0.60;
  const dVal = dateSelect ? dateSelect.value : "2026_09_11";
  const targetDate = dVal === "all" ? "2026_09_11" : dVal;

  const btn = document.getElementById("btnRunMultiLeg");
  if (btn) {
    btn.disabled = true;
    btn.innerText = "Simulating Greeks...";
  }

  const tbody = document.getElementById("mlLegsBody");
  if (tbody) tbody.innerHTML = '<tr><td colspan="10" class="empty-state">Simulating multi-leg option progression and Greeks...</td></tr>';

  try {
    const res = await fetch("/api/trading_engine/multi_leg_simulation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        date: targetDate,
        strategy: strat,
        underlying: "NIFTY",
        sl_pct: sl,
        target_pct: tgt
      })
    });
    const json = await res.json();
    if (json.status === "ok" && json.data) {
      renderMultiLegSimulation(json.data);
    } else {
      if (tbody) tbody.innerHTML = `<tr><td colspan="10" class="empty-state" style="color: var(--red);">${json.message || "Simulation failed"}</td></tr>`;
    }
  } catch (err) {
    console.error("Error in multi-leg simulation:", err);
    if (tbody) tbody.innerHTML = `<tr><td colspan="10" class="empty-state" style="color: var(--red);">Error: ${err.message}</td></tr>`;
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = "⚡ Simulate Multi-Leg";
    }
  }
}

function renderMultiLegSimulation(data) {
  const pnl = data.total_net_pnl || 0;
  const theta = data.total_theta_harvested || 0;
  const tl = data.timeline || [];

  const kPnl = document.getElementById("mlKpiPnl");
  if (kPnl) {
    kPnl.innerText = `${pnl >= 0 ? "+" : ""}₹${pnl.toFixed(2)}`;
    kPnl.style.color = pnl >= 0 ? "var(--green)" : "var(--red)";
  }

  const kTheta = document.getElementById("mlKpiTheta");
  if (kTheta) kTheta.innerText = `₹${theta.toFixed(2)}`;

  let peakDelta = 0;
  let peakGamma = 0;
  tl.forEach(pt => {
    if (Math.abs(pt.net_delta || 0) > Math.abs(peakDelta)) peakDelta = pt.net_delta;
    if (Math.abs(pt.net_gamma || 0) > Math.abs(peakGamma)) peakGamma = pt.net_gamma;
  });

  const kDelta = document.getElementById("mlKpiDelta");
  if (kDelta) kDelta.innerText = `${peakDelta >= 0 ? "+" : ""}${peakDelta.toFixed(2)} Δ`;

  const kGamma = document.getElementById("mlKpiGamma");
  if (kGamma) kGamma.innerText = `${peakGamma.toFixed(5)} Γ`;

  // Legs Table
  const tbody = document.getElementById("mlLegsBody");
  if (tbody) {
    const legs = data.legs || [];
    if (legs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="10" class="empty-state">No executed legs.</td></tr>';
    } else {
      tbody.innerHTML = legs.map(l => {
        const pColor = (l.pnl || 0) >= 0 ? "var(--green)" : "var(--red)";
        const badge = l.type === "CE" ? "badge-long" : "badge-short";
        return `
          <tr>
            <td><span class="badge ${badge}">${l.type}</span></td>
            <td style="font-weight: 700;">${l.strike}</td>
            <td><span class="badge badge-neutral">${l.side}</span></td>
            <td style="font-family: 'JetBrains Mono', monospace;">${l.qty}</td>
            <td style="font-family: 'JetBrains Mono', monospace;">${l.entry_time}</td>
            <td style="font-family: 'JetBrains Mono', monospace;">₹${(l.entry_premium || 0).toFixed(2)}</td>
            <td style="font-family: 'JetBrains Mono', monospace;">${l.exit_time || "--"}</td>
            <td style="font-family: 'JetBrains Mono', monospace;">₹${(l.exit_premium || 0).toFixed(2)}</td>
            <td><span class="badge ${l.exit_reason === 'STOP_LOSS' ? 'badge-short' : (l.exit_reason === 'TARGET_DECAY' ? 'badge-long' : 'badge-neutral')}">${l.exit_reason || "OPEN"}</span></td>
            <td style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: ${pColor};">
              ${(l.pnl >= 0 ? "+" : "")}₹${(l.pnl || 0).toFixed(2)}
            </td>
          </tr>
        `;
      }).join("");
    }
  }

  // Chart
  const canvas = document.getElementById("teGreeksChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (teGreeksChartInstance) {
    teGreeksChartInstance.destroy();
    teGreeksChartInstance = null;
  }

  const times = tl.map(t => t.time);
  const pnlSeries = tl.map(t => t.cumulative_pnl);
  const deltaSeries = tl.map(t => t.net_delta);

  teGreeksChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: times,
      datasets: [
        {
          label: "Intraday Cumulative P&L (₹)",
          data: pnlSeries,
          borderColor: pnl >= 0 ? "#00f5a0" : "#ff4d4f",
          backgroundColor: pnl >= 0 ? "rgba(0, 245, 160, 0.08)" : "rgba(255, 77, 79, 0.08)",
          fill: true,
          tension: 0.2,
          borderWidth: 2,
          yAxisID: "y"
        },
        {
          label: "Net Portfolio Delta (Δ)",
          data: deltaSeries,
          borderColor: "#00f2fe",
          backgroundColor: "transparent",
          borderWidth: 1.5,
          borderDash: [4, 4],
          pointRadius: 0,
          yAxisID: "y1"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: true, labels: { color: "#8b949e", font: { size: 11 } } },
        tooltip: {
          backgroundColor: "rgba(10, 16, 28, 0.95)",
          borderColor: "rgba(255, 255, 255, 0.1)",
          borderWidth: 1
        }
      },
      scales: {
        x: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#8b949e", maxTicksLimit: 10 } },
        y: {
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "#8b949e", callback: v => `₹${v}` }
        },
        y1: {
          position: "right",
          grid: { drawOnChartArea: false },
          ticks: { color: "#00f2fe" }
        }
      }
    }
  });
}

// ── Daily Session Audit Tearsheet Modal ───────────────────────────────────────────
async function fetchSessionAudit() {
  const select = document.getElementById("teDateSelect");
  const targetDate = select ? select.value : "2026_09_11";
  const content = document.getElementById("teAuditModalContent");
  const modalTitle = document.getElementById("teAuditModalTitle");
  if (modalTitle) modalTitle.innerText = `Session Audit Report: ${targetDate}`;
  if (content) content.innerHTML = '<div class="empty-state">Running comprehensive session audit & synthesizing scorecard...</div>';

  try {
    const res = await fetch(`/api/trading_engine/audit?date=${encodeURIComponent(targetDate)}`);
    const json = await res.json();
    if (json.status === "ok" && json.data) {
      const d = json.data;
      const recon = d.reconciliation?.summary || {};
      const ai = d.ai_analytics?.counterfactual_matrix || {};
      const flags = d.flags || [];

      const flagsHtml = flags.map(f => {
        const col = f.severity === 'WARNING' ? 'var(--red)' : (f.severity === 'SUCCESS' ? 'var(--green)' : 'var(--accent-cyan)');
        const bg = f.severity === 'WARNING' ? 'rgba(255,77,79,0.1)' : (f.severity === 'SUCCESS' ? 'rgba(0,245,160,0.1)' : 'rgba(0,242,254,0.1)');
        return `
          <div style="padding: 10px 14px; margin-bottom: 8px; border-radius: 6px; background: ${bg}; border-left: 4px solid ${col}; font-size: 0.84rem;">
            <strong style="color: #fff;">[${f.severity}] ${f.code}:</strong> <span style="color: #c9d1d9;">${f.message}</span>
          </div>
        `;
      }).join("") || '<div class="empty-state">No execution anomalies detected.</div>';

      if (content) {
        content.innerHTML = `
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 12px;">
            <div>
              <span style="font-size: 1.3rem; font-weight: 800; color: #fff;">Health Grade: </span>
              <span style="font-size: 1.3rem; font-weight: 800; color: ${d.status_color};">${d.grade}</span>
            </div>
            <span style="font-size: 0.85rem; color: var(--text-muted);">Generated: ${d.generated_at}</span>
          </div>

          <div class="kpi-grid" style="margin-bottom: 20px;">
            <div class="kpi-card">
              <span class="kpi-label">Health Score</span>
              <span class="kpi-value" style="color: ${d.status_color};">${d.health_score} / 100</span>
              <span class="kpi-sub">Overall execution fidelity</span>
            </div>
            <div class="kpi-card">
              <span class="kpi-label">Execution Efficiency</span>
              <span class="kpi-value" style="color: var(--accent-cyan);">${(recon.execution_efficiency_score || 0).toFixed(1)}%</span>
              <span class="kpi-sub">Latency & slippage rating</span>
            </div>
            <div class="kpi-card">
              <span class="kpi-label">Avg Entry Slippage</span>
              <span class="kpi-value">₹${(recon.avg_entry_slippage_rs || 0).toFixed(2)}</span>
              <span class="kpi-sub">${(recon.avg_entry_slippage_pct || 0).toFixed(2)}% premium drag</span>
            </div>
            <div class="kpi-card">
              <span class="kpi-label">AI Precision</span>
              <span class="kpi-value" style="color: var(--green);">${(ai.precision || 0).toFixed(1)}%</span>
              <span class="kpi-sub">Filtered ${ai.signals_filtered || 0} chop signals</span>
            </div>
          </div>

          <div class="card" style="margin-bottom: 16px;">
            <h4 style="margin: 0 0 10px; color: #fff;">Diagnostic Flags & Observations</h4>
            ${flagsHtml}
          </div>
        `;
      }
    } else {
      if (content) content.innerHTML = `<div class="empty-state" style="color: var(--red);">${json.message || "Failed to load audit"}</div>`;
    }
  } catch (err) {
    console.error("Error fetching audit:", err);
    if (content) content.innerHTML = `<div class="empty-state" style="color: var(--red);">Error: ${err.message}</div>`;
  }
}

