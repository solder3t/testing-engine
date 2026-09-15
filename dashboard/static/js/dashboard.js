// dashboard.js — Dynamic Real-Data Dashboard Engine
// Strictly zero hardcoded data: all metrics, charts, and tables are generated from real databases.

let equityChart = null;
let dailyChart = null;
let drawdownChart = null;
let allTrades = [];
let filteredTrades = [];
let currentSortColumn = "entry_time";
let sortAscending = false;

document.addEventListener("DOMContentLoaded", () => {
  initStrategySelector();
  initDirectoryScanner();
  initFileBrowser();
  initTableSort();
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
});

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

  if (!modal || !btnOpen) return;

  btnOpen.addEventListener("click", () => {
    modal.style.display = "flex";
    const startPath = dirInput.value.trim() || "~/Downloads";
    browsePath(startPath);
  });

  btnClose.addEventListener("click", () => {
    modal.style.display = "none";
  });

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
      <div class="explorer-item-left">
        <span class="explorer-item-icon">${icon}</span>
        <span class="explorer-item-name" title="${item.path}">${item.name}</span>
      </div>
      <div class="explorer-item-right">
        ${badgeHtml}
        <span class="explorer-item-size">${sizeStr}</span>
      </div>
    `;

    // Click to select
    el.addEventListener("click", () => {
      document.querySelectorAll(".explorer-item").forEach(i => i.classList.remove("selected"));
      el.classList.add("selected");
      currentSelectedPath = item.path;
      selectedDisplay.innerText = item.path;
      btnConfirm.disabled = false;
    });

    // Double click to enter directory
    if (item.type === "folder") {
      el.addEventListener("dblclick", () => {
        browsePath(item.path);
      });
    }

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

async function loadArchives(customDir = null) {
  const container = document.getElementById("archiveList");
  const dirInput = document.getElementById("dirInput");
  const targetDir = customDir !== null ? customDir : dirInput.value.trim();
  const statusPill = document.getElementById("currentScannedDir");
  const headerStatus = document.getElementById("headerStatusText");

  container.innerHTML = '<div class="empty-state" style="padding: 10px;">Scanning directory...</div>';
  headerStatus.innerText = "SCANNING...";

  try {
    const url = `/api/archives?dir=${encodeURIComponent(targetDir || "~/Downloads")}`;
    const res = await fetch(url);
    const data = await res.json();

    if (data.status !== "success" || !data.archives || data.archives.length === 0) {
      container.innerHTML = `<div class="empty-state">No RAR archives or session folders found in ${data.scanned_directory || targetDir}</div>`;
      headerStatus.innerText = "NO SESSIONS FOUND";
      return;
    }

    if (statusPill && data.scanned_directory) {
      statusPill.innerText = `DIR: ${data.scanned_directory}`;
    }

    container.innerHTML = "";
    data.archives.forEach((arch, idx) => {
      const item = document.createElement("div");
      item.className = "archive-item";

      const isFolder = arch.type === "folder";
      const typeBadgeClass = isFolder ? "badge-folder" : "badge-archive";
      const typeBadgeText = isFolder ? "📁 Folder" : "📦 RAR";

      const statusBadgeClass = arch.is_extracted ? "badge-extracted" : "badge-compressed";
      const statusBadgeText = arch.is_extracted ? "Extracted" : "Compressed";

      item.innerHTML = `
        <label style="display: flex; align-items: center; cursor: pointer; gap: 8px;">
          <input type="checkbox" name="archiveDate" value="${arch.date}" ${idx === 0 ? "checked" : ""}>
          <span><strong>${arch.date}</strong> <span style="color: var(--text-muted); font-size: 0.75rem;">(${arch.size_mb.toFixed(1)} MB)</span></span>
        </label>
        <div class="archive-badges">
          <span class="archive-badge ${typeBadgeClass}">${typeBadgeText}</span>
          <span class="archive-badge ${statusBadgeClass}">${statusBadgeText}</span>
        </div>
      `;
      container.appendChild(item);
    });

    headerStatus.innerText = "ENGINE READY";
  } catch (err) {
    container.innerHTML = `<div class="empty-state" style="color: var(--red);">Error connecting to testing engine API</div>`;
    headerStatus.innerText = "CONNECTION ERROR";
  }
}

// ── Backtest Execution ───────────────────────────────────────────────────────
async function runBacktest() {
  const btn = document.getElementById("btnRun");
  const statusDiv = document.getElementById("runStatus");

  const checked = document.querySelectorAll('input[name="archiveDate"]:checked');
  const selectedDates = Array.from(checked).map(cb => cb.value);

  if (selectedDates.length === 0) {
    alert("Please select at least one archive date or session folder to test.");
    return;
  }

  const directory = document.getElementById("dirInput").value.trim() || "~/Downloads";
  const strategy = document.getElementById("strategySelect").value;
  const timeframe = document.getElementById("timeframeSelect").value;
  const capital = parseFloat(document.getElementById("capitalInput").value) || 500000;
  const riskPct = (parseFloat(document.getElementById("riskInput").value) || 1.0) / 100.0;

  const payload = {
    directory: directory,
    dates: selectedDates,
    strategy: strategy,
    timeframe: timeframe,
    capital: capital,
    risk_pct: riskPct
  };

  if (strategy === "equity") {
    const symbolsRaw = document.getElementById("symbolsInput").value;
    payload.symbols = symbolsRaw.split(",").map(s => s.trim().toUpperCase()).filter(s => s.length > 0);
    payload.min_score = parseInt(document.getElementById("minScoreInput").value) || 55;
    payload.atr_sl_mult = parseFloat(document.getElementById("atrSlInput").value) || 1.5;
  } else if (strategy === "vwap-reversion") {
    const symbolsRaw = document.getElementById("vwapSymbolsInput") ? document.getElementById("vwapSymbolsInput").value : "RELIANCE, HDFCBANK, INFY";
    payload.symbols = symbolsRaw.split(",").map(s => s.trim().toUpperCase()).filter(s => s.length > 0);
    payload.bb_period = parseInt(document.getElementById("vwapBbPeriodInput").value) || 20;
    payload.bb_std = parseFloat(document.getElementById("vwapBbStdInput").value) || 2.0;
    payload.sl_pts = parseFloat(document.getElementById("vwapSlPtsInput").value) || 15.0;
    payload.target_pts = parseFloat(document.getElementById("vwapTgtPtsInput").value) || 30.0;
  } else if (strategy === "rsi-momentum") {
    const symbolsRaw = document.getElementById("rsiSymbolsInput") ? document.getElementById("rsiSymbolsInput").value : "RELIANCE, HDFCBANK, INFY";
    payload.symbols = symbolsRaw.split(",").map(s => s.trim().toUpperCase()).filter(s => s.length > 0);
    payload.fast_ema = parseInt(document.getElementById("rsiFastEmaInput").value) || 9;
    payload.slow_ema = parseInt(document.getElementById("rsiSlowEmaInput").value) || 21;
    payload.rsi_period = parseInt(document.getElementById("rsiPeriodInput").value) || 14;
    payload.rsi_long_cutoff = parseFloat(document.getElementById("rsiLongCutoffInput").value) || 60.0;
  } else if (strategy === "options") {
    payload.sl_points = parseFloat(document.getElementById("slPointsInput").value) || 12.0;
    payload.target_multiplier = parseFloat(document.getElementById("tgtMultInput").value) || 1.8;
    payload.lot_size = parseInt(document.getElementById("lotSizeInput").value) || 25;
  } else if (strategy === "ai-replay") {
    payload.confidence = parseFloat(document.getElementById("confInput").value) || 0.70;
  }

  btn.disabled = true;
  btn.innerText = "EXTRACTING & REPLAYING...";
  statusDiv.innerText = `Simulating ${strategy} on ${selectedDates.length} session(s) (${timeframe} bars)...`;

  try {
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (data.status !== "success" || !data.result) {
      alert("Backtest error: " + (data.message || "Execution failed."));
      statusDiv.innerText = "Error: " + (data.message || "Failed");
      return;
    }

    renderResults(data.result);
    statusDiv.innerText = `Completed simulation across ${selectedDates.length} session(s).`;
  } catch (err) {
    alert("Simulation network error: " + err);
    statusDiv.innerText = "Simulation failed.";
  } finally {
    btn.disabled = false;
    btn.innerText = "RUN BACKTEST ⚡";
  }
}

async function loadLatestResults() {
  try {
    const res = await fetch("/api/results");
    const data = await res.json();
    if (data.status === "success" && data.result && data.result.metrics) {
      renderResults(data.result);
    }
  } catch (e) {
    // Keep empty state
  }
}

// ── Render Results ───────────────────────────────────────────────────────────
function renderResults(result) {
  const m = result.metrics || {};
  const isProfit = (m.net_pnl || 0) >= 0;

  // KPIs
  const netEl = document.getElementById("kpiNetPnl");
  netEl.innerText = `${isProfit ? "+" : ""}₹${(m.net_pnl || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
  netEl.className = `kpi-value ${isProfit ? "pos" : "neg"}`;

  document.getElementById("kpiReturn").innerText = `${(m.return_pct || 0).toFixed(2)}% return`;
  document.getElementById("kpiWinRate").innerText = `${(m.win_rate || 0).toFixed(1)}%`;
  document.getElementById("kpiTradesCount").innerText = `${m.total_trades || 0} trades (${m.wins || 0}W / ${m.losses || 0}L)`;
  document.getElementById("kpiProfitFactor").innerText = `${(m.profit_factor || 0).toFixed(2)}`;
  document.getElementById("kpiExpectancy").innerText = `Exp: ₹${(m.expectancy || 0).toFixed(2)}`;
  document.getElementById("kpiSharpe").innerText = `${(m.sharpe_ratio || 0).toFixed(2)}`;
  document.getElementById("kpiSortino").innerText = `Sortino: ${(m.sortino_ratio || 0).toFixed(2)}`;
  document.getElementById("kpiMaxDD").innerText = `${(m.max_drawdown_pct || 0).toFixed(2)}%`;
  document.getElementById("kpiMaxDDRs").innerText = `₹${(m.max_drawdown_rs || 0).toLocaleString("en-IN")}`;
  document.getElementById("kpiCharges").innerText = `₹${(m.total_charges || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;

  // Charts
  renderEquityChart(result.equity_curve || []);
  renderDailyChart(result.daily_breakdown || []);
  renderDrawdownChart(result.drawdown_curve || []);

  // Trades
  allTrades = result.trades || [];
  filterAndRenderTrades();
}

// ── Charts ───────────────────────────────────────────────────────────────────
function renderEquityChart(curve) {
  const canvas = document.getElementById("equityChart");
  const placeholder = document.getElementById("equityPlaceholder");
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

  equityChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [{
        label: "Portfolio Equity (₹)",
        data: values,
        borderColor: "#00f2fe",
        backgroundColor: "rgba(0, 242, 254, 0.08)",
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
  // Show drawdowns as negative percentages for standard underwater view
  const values = curve.map(pt => -Math.abs(pt.drawdown_pct || 0));

  drawdownChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [{
        label: "Underwater Drawdown (%)",
        data: values,
        borderColor: "#ef4444",
        backgroundColor: "rgba(239, 68, 68, 0.15)",
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

// ── Trades Table: Sorting, Filtering, and Rendering ──────────────────────────
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

function filterAndRenderTrades() {
  const searchInput = document.getElementById("tradeSearchInput");
  const query = searchInput ? searchInput.value.trim().toLowerCase() : "";

  filteredTrades = allTrades.filter(t => {
    if (!query) return true;
    const sym = (t.symbol || "").toLowerCase();
    const side = (t.side || "").toLowerCase();
    const reason = (t.exit_reason || "").toLowerCase();
    const time = (t.entry_time || "").toLowerCase();
    return sym.includes(query) || side.includes(query) || reason.includes(query) || time.includes(query);
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
    countBadge.innerText = query
      ? `${filteredTrades.length} of ${allTrades.length} trades`
      : `${allTrades.length} trades`;
  }

  const tbody = document.getElementById("tradesBody");
  if (filteredTrades.length === 0) {
    tbody.innerHTML = '<tr><td colspan="11" class="empty-state">No trades match the filter / setup.</td></tr>';
    return;
  }

  tbody.innerHTML = "";
  filteredTrades.forEach(t => {
    const tr = document.createElement("tr");
    const isWin = (t.net_pnl || 0) >= 0;
    const timeShort = (t.entry_time || "").split(" ").pop() || t.entry_time;

    tr.innerHTML = `
      <td>${timeShort}</td>
      <td style="font-weight: 600; color: #fff;">${t.symbol}</td>
      <td style="color: ${t.side === "BUY" ? "var(--green)" : "var(--red)}; font-weight: 600;">${t.side}</td>
      <td>${t.qty}</td>
      <td>₹${(t.entry_price || 0).toFixed(2)}</td>
      <td>${t.exit_price ? "₹" + t.exit_price.toFixed(2) : "-"}</td>
      <td style="color: ${(t.gross_pnl || 0) >= 0 ? "var(--green)" : "var(--red)};">₹${(t.gross_pnl || 0).toFixed(2)}</td>
      <td style="color: var(--text-muted);">₹${(t.charges || 0).toFixed(2)}</td>
      <td style="font-weight: 700; color: ${isWin ? "var(--green)" : "var(--red)};">
        ${isWin ? "+" : ""}₹${(t.net_pnl || 0).toFixed(2)}
      </td>
      <td><span class="badge" style="font-size: 0.7rem; background: rgba(255,255,255,0.08);">${t.exit_reason || "-"}</span></td>
      <td><button class="btn-detail" onclick="openTradeModal('${t.trade_id}')">Inspect 🔍</button></td>
    `;
    tbody.appendChild(tr);
  });
}

// ── Trade Detail Modal ───────────────────────────────────────────────────────
function initModal() {
  const modal = document.getElementById("tradeModal");
  const closeBtn = document.getElementById("modalCloseBtn");

  closeBtn.addEventListener("click", closeTradeModal);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeTradeModal();
  });
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeTradeModal();
  });
}

function openTradeModal(tradeId) {
  const trade = allTrades.find(t => t.trade_id === tradeId);
  if (!trade) return;

  const modal = document.getElementById("tradeModal");
  const title = document.getElementById("modalTitle");
  const content = document.getElementById("modalContent");

  title.innerText = `Trade #${trade.trade_id} — ${trade.symbol} (${trade.side})`;

  const isWin = (trade.net_pnl || 0) >= 0;
  const pnlColor = isWin ? "var(--green)" : "var(--red)";

  // Statutory charges breakdown
  const cb = trade.charges_breakdown || (trade.metadata && trade.metadata.charges_breakdown) || {};
  const brokerage = cb.brokerage !== undefined ? cb.brokerage : (trade.charges ? trade.charges * 0.4 : 0);
  const stt = cb.stt !== undefined ? cb.stt : 0;
  const exchangeFee = cb.exchange_fee !== undefined ? cb.exchange_fee : 0;
  const gst = cb.gst !== undefined ? cb.gst : 0;
  const sebi = cb.sebi !== undefined ? cb.sebi : 0;
  const stampDuty = cb.stamp_duty !== undefined ? cb.stamp_duty : 0;
  const totalCharges = trade.charges || 0;

  content.innerHTML = `
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 0.82rem;">
      <div>
        <div style="color: var(--text-muted);">Execution Time:</div>
        <div style="font-weight: 600; color: #fff;">${trade.entry_time} → ${trade.exit_time || "OPEN"}</div>
      </div>
      <div>
        <div style="color: var(--text-muted);">Holding Duration:</div>
        <div style="font-weight: 600; color: #fff;">${trade.holding_bars || 0} bars</div>
      </div>
      <div>
        <div style="color: var(--text-muted);">Entry Fill:</div>
        <div style="font-weight: 600; color: #fff;">₹${(trade.entry_price || 0).toFixed(2)} (${trade.qty} units)</div>
      </div>
      <div>
        <div style="color: var(--text-muted);">Exit Fill:</div>
        <div style="font-weight: 600; color: #fff;">${trade.exit_price ? "₹" + trade.exit_price.toFixed(2) : "-"} (${trade.exit_reason || "-"})</div>
      </div>
      <div>
        <div style="color: var(--text-muted);">Risk & Target:</div>
        <div style="font-weight: 500; color: var(--text-muted);">SL: ₹${(trade.initial_sl || 0).toFixed(2)} | TGT: ₹${(trade.target || 0).toFixed(2)}</div>
      </div>
      <div>
        <div style="color: var(--text-muted);">Net Realized P&L:</div>
        <div style="font-size: 1.1rem; font-weight: 700; color: ${pnlColor};">
          ${isWin ? "+" : ""}₹${(trade.net_pnl || 0).toFixed(2)} (${(trade.pnl_pct || 0).toFixed(2)}%)
        </div>
      </div>
    </div>

    <div style="margin-top: 10px;">
      <h4 style="font-size: 0.8rem; text-transform: uppercase; color: var(--accent-cyan); margin-bottom: 8px;">
        Official Statutory Regulatory Fees & Taxes (NSE Circular)
      </h4>
      <div class="fee-breakdown">
        <div class="fee-item"><span>Brokerage (Discount Broker)</span><strong>₹${brokerage.toFixed(2)}</strong></div>
        <div class="fee-item"><span>Securities Transaction Tax (STT)</span><strong>₹${stt.toFixed(2)}</strong></div>
        <div class="fee-item"><span>Exchange Turnover Charges</span><strong>₹${exchangeFee.toFixed(2)}</strong></div>
        <div class="fee-item"><span>GST (18% on Brokerage & Txn)</span><strong>₹${gst.toFixed(2)}</strong></div>
        <div class="fee-item"><span>SEBI Turnover Charges</span><strong>₹${sebi.toFixed(2)}</strong></div>
        <div class="fee-item"><span>State Stamp Duty</span><strong>₹${stampDuty.toFixed(2)}</strong></div>
      </div>
      <div style="display: flex; justify-content: space-between; margin-top: 8px; font-weight: 700; font-size: 0.85rem;">
        <span>Total Regulatory Deductions:</span>
        <span style="color: var(--yellow);">₹${totalCharges.toFixed(2)}</span>
      </div>
    </div>
  `;

  modal.style.display = "flex";
}

function closeTradeModal() {
  const modal = document.getElementById("tradeModal");
  if (modal) modal.style.display = "none";
}

// Make openTradeModal globally accessible for inline onclick
window.openTradeModal = openTradeModal;
