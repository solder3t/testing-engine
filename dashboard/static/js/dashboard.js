// dashboard.js — Institutional Real-Data Dashboard Engine (BOT 2.0 Inspired)
// Strictly zero hardcoded data: all metrics, charts, and tables are generated from real databases.

let equityChart = null;
let dailyChart = null;
let drawdownChart = null;
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

  // Load default directory
  loadArchives();
  loadLatestResults();

  document.getElementById("btnRun").addEventListener("click", runBacktest);
  document.getElementById("btnExportCsv").addEventListener("click", () => {
    window.location.href = "/api/export_csv";
  });

  const searchInput = document.getElementById("tradeSearchInput");
  if (searchInput) {
    searchInput.addEventListener("input", () => {
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
  } else if (tabId === "tabExplorer") {
    renderDataExplorer(lastRawArchives);
  }
}
window.switchTab = switchTab;

// ── Strategy Selector ────────────────────────────────────────────────────────
function initStrategySelector() {
  const select = document.getElementById("strategySelect");
  const eqGroup = document.getElementById("equityParams");
  const vwapGroup = document.getElementById("vwapParams");
  const rsiGroup = document.getElementById("rsiParams");
  const optGroup = document.getElementById("optionsParams");
  const aiGroup = document.getElementById("aiParams");

  const hideAll = () => {
    eqGroup.style.display = "none";
    if (vwapGroup) vwapGroup.style.display = "none";
    if (rsiGroup) rsiGroup.style.display = "none";
    optGroup.style.display = "none";
    aiGroup.style.display = "none";
  };

  select.addEventListener("change", () => {
    hideAll();
    const val = select.value;
    if (val === "equity") {
      eqGroup.style.display = "block";
    } else if (val === "vwap-reversion" && vwapGroup) {
      vwapGroup.style.display = "block";
    } else if (val === "rsi-momentum" && rsiGroup) {
      rsiGroup.style.display = "block";
    } else if (val === "options") {
      optGroup.style.display = "block";
    } else if (val === "ai-replay") {
      aiGroup.style.display = "block";
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
    payload.symbols = document.getElementById("symbolsInput").value.split(",").map(s => s.trim()).filter(Boolean);
  } else if (strat === "vwap-reversion") {
    payload.bb_period = parseInt(document.getElementById("vwapBbPeriodInput").value) || 20;
    payload.bb_std = parseFloat(document.getElementById("vwapBbStdInput").value) || 2.0;
    payload.sl_pts = parseFloat(document.getElementById("vwapSlPtsInput").value) || 15.0;
    payload.target_pts = parseFloat(document.getElementById("vwapTgtPtsInput").value) || 30.0;
    payload.symbols = document.getElementById("vwapSymbolsInput").value.split(",").map(s => s.trim()).filter(Boolean);
  } else if (strat === "rsi-momentum") {
    payload.fast_ema = parseInt(document.getElementById("rsiFastEmaInput").value) || 9;
    payload.slow_ema = parseInt(document.getElementById("rsiSlowEmaInput").value) || 21;
    payload.rsi_period = parseInt(document.getElementById("rsiPeriodInput").value) || 14;
    payload.rsi_long_cutoff = parseFloat(document.getElementById("rsiLongCutoffInput").value) || 60.0;
    payload.symbols = document.getElementById("rsiSymbolsInput").value.split(",").map(s => s.trim()).filter(Boolean);
  } else if (strat === "options") {
    payload.sl_points = parseFloat(document.getElementById("optionSlInput").value) || 12.0;
    payload.target_multiplier = parseFloat(document.getElementById("optionTgtInput").value) || 1.8;
    payload.lot_size = parseInt(document.getElementById("optionLotSizeInput").value) || 25;
  } else if (strat === "ai-replay") {
    payload.confidence = parseFloat(document.getElementById("aiConfidenceInput").value) || 0.70;
  }

  btn.disabled = true;
  btn.innerText = "⏳ SIMULATING...";
  status.innerText = `Replaying real recorded ticks for [${selectedDates.join(", ")}]...`;
  status.style.color = "var(--accent-cyan)";
  if (headerStatus) headerStatus.innerText = "BACKTEST RUNNING";

  try {
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (data.status === "success") {
      status.innerText = `Simulation complete! Processed ${data.trades ? data.trades.length : 0} executed trades.`;
      status.style.color = "var(--green)";
      renderResults(data);
      // Auto-switch to Results & Analytics tab
      switchTab("tabAnalytics");
    } else {
      status.innerText = `Error: ${data.message}`;
      status.style.color = "var(--red)";
    }
  } catch (err) {
    status.innerText = `Execution failed: ${err}`;
    status.style.color = "var(--red)";
  } finally {
    btn.disabled = false;
    btn.innerText = "⚡ RUN BACKTEST";
    if (headerStatus) headerStatus.innerText = "ENGINE READY";
  }
}

// ── Load Latest Results on Initial Launch ────────────────────────────────────
async function loadLatestResults() {
  try {
    const res = await fetch("/api/results");
    const data = await res.json();
    if (data.status === "success" && data.metrics) {
      renderResults(data);
    }
  } catch (err) {
    // Fresh session, no latest run yet
  }
}

// ── Render Results: Institutional KPIs, Charts, and Trades Table ─────────────
function renderResults(data) {
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
  const maxDDEl = document.getElementById("kpiMaxDD");
  const maxDDRsEl = document.getElementById("kpiMaxDDRs");
  const chargesEl = document.getElementById("kpiCharges");

  const netPnl = m.net_pnl || 0.0;
  const isProfit = netPnl >= 0;
  netPnlEl.innerText = `${isProfit ? "+" : ""}₹${netPnl.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
  netPnlEl.className = `kpi-value ${isProfit ? "pos" : "neg"}`;

  const retPct = m.return_pct || 0.0;
  returnEl.innerText = `${retPct >= 0 ? "+" : ""}${retPct.toFixed(2)}% on capital`;
  returnEl.style.color = isProfit ? "var(--green)" : "var(--red)";

  winRateEl.innerText = `${(m.win_rate || 0.0).toFixed(1)}%`;
  tradesCountEl.innerText = `${m.total_trades || 0} trades (${m.wins || 0}W / ${m.losses || 0}L)`;

  pfEl.innerText = (m.profit_factor || 0.0).toFixed(2);
  expEl.innerText = `Exp: ₹${(m.expectancy || 0.0).toFixed(2)}`;

  sharpeEl.innerText = (m.sharpe_ratio || 0.0).toFixed(2);
  sortinoEl.innerText = `Sortino: ${(m.sortino_ratio || 0.0).toFixed(2)}`;

  maxDDEl.innerText = `${(m.max_drawdown_pct || 0.0).toFixed(2)}%`;
  maxDDRsEl.innerText = `₹${(m.max_drawdown_rs || 0.0).toLocaleString("en-IN", { minimumFractionDigits: 2 })} peak-to-trough`;

  chargesEl.innerText = `₹${(m.total_charges || 0.0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;

  // 2. Charts
  renderEquityChart(m.equity_curve || []);
  renderDailyChart(m.daily_pnls || []);
  renderDrawdownChart(m.drawdown_curve || []);

  // 3. Trades Table & Trade Inspector
  filterAndRenderTrades();

  // If trades exist, auto-select first trade in Inspector
  if (allTrades.length > 0) {
    inspectTrade(allTrades[0].trade_id);
  }
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

// ── Trades Table: Sorting, Quick Filter Pills, and Inspector ─────────────────
function initTableSort() {
  const headers = document.querySelectorAll("th[data-sort]");
  headers.forEach(th => {
    th.addEventListener("click", () => {
      const col = th.getAttribute("data-sort");
      if (currentSortColumn === col) {
        sortAscending = !sortAscending;
      } else {
        currentSortColumn = col;
        sortAscending = false; // default descending for most recent/highest
      }
      filterAndRenderTrades();
    });
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
}

function filterAndRenderTrades() {
  const searchInput = document.getElementById("tradeSearchInput");
  const query = searchInput ? searchInput.value.trim().toLowerCase() : "";

  filteredTrades = allTrades.filter(t => {
    // 1. Text Search Filter
    if (query) {
      const sym = (t.symbol || "").toLowerCase();
      const side = (t.side || "").toLowerCase();
      const reason = (t.exit_reason || "").toLowerCase();
      const time = (t.entry_time || "").toLowerCase();
      const matchesSearch = sym.includes(query) || side.includes(query) || reason.includes(query) || time.includes(query);
      if (!matchesSearch) return false;
    }

    // 2. Pill Category Filter
    if (currentTradeFilter === "win") {
      return (t.net_pnl || 0) > 0;
    } else if (currentTradeFilter === "loss") {
      return (t.net_pnl || 0) <= 0;
    } else if (currentTradeFilter === "buy") {
      return (t.side || "").toUpperCase() === "BUY";
    } else if (currentTradeFilter === "sell") {
      return (t.side || "").toUpperCase() === "SELL";
    }

    return true;
  });

  // Sort
  filteredTrades.sort((a, b) => {
    let valA = a[currentSortColumn];
    let valB = b[currentSortColumn];

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
    countBadge.innerText = (query || currentTradeFilter !== "all")
      ? `${filteredTrades.length} of ${allTrades.length} trades`
      : `${allTrades.length} trades`;
  }

  const tbody = document.getElementById("tradesBody");
  if (filteredTrades.length === 0) {
    tbody.innerHTML = '<tr><td colspan="11" class="empty-state">No trades match the active filter or search query.</td></tr>';
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
    const timeShort = (t.entry_time || "").split(" ").pop() || t.entry_time;

    tr.innerHTML = `
      <td>${timeShort}</td>
      <td style="font-weight: 600; color: #fff;">${t.symbol}</td>
      <td style="color: ${t.side === "BUY" ? "var(--green)" : "var(--red)"}; font-weight: 600;">${t.side}</td>
      <td>${t.qty}</td>
      <td>₹${(t.entry_price || 0).toFixed(2)}</td>
      <td>${t.exit_price ? "₹" + t.exit_price.toFixed(2) : "-"}</td>
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
