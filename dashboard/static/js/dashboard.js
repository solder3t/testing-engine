// Centralized Chart Registry with Lifecycle Management (CHART-01)
const ChartRegistry = {
  charts: {},
  register(name, chartInstance) {
    if (this.charts[name]) {
      try { this.charts[name].destroy(); } catch (e) {}
    }
    this.charts[name] = chartInstance;
    return chartInstance;
  },
  destroy(name) {
    if (this.charts[name]) {
      try { this.charts[name].destroy(); } catch (e) {}
      delete this.charts[name];
    }
  },
  destroyAll() {
    Object.keys(this.charts).forEach(name => this.destroy(name));
  }
};
window.ChartRegistry = ChartRegistry;

let equityChart = null;
let dailyChart = null;
let drawdownChart = null;
let hourlyChart = null;
let outcomeChart = null;
let pnlDistChart = null;
let allTrades = [];
let filteredTrades = [];
let currentSortColumn = "entry_time";
let sortAscending = false;
let currentTradeFilter = "all";
let currentSelectedTradeId = null;
let lastRawArchives = [];
let isBacktestRunning = false;
let latest_run_cache = null;

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
  initMassIterationLab();

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

  // DOM-01: Decoupled event listeners
  const btnLaunchProfile = document.getElementById("btnLaunchChromeProfile");
  if (btnLaunchProfile) {
    btnLaunchProfile.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/open_browser", { method: "POST" });
        const data = await res.json();
        if (data.status === "success") {
          showToast("Opened dashboard in Chrome profile!", "success");
        } else {
          showToast("Failed to launch Chrome profile", "warning");
        }
      } catch (err) {
        showToast("Error contacting browser launcher: " + err.message, "error");
      }
    });
  }

  const btnBrowse = document.getElementById("btnBrowseDir");
  if (btnBrowse) {
    btnBrowse.addEventListener("click", openFileBrowser);
  }

  const btnExpBrowse = document.getElementById("btnExplorerBrowse");
  if (btnExpBrowse) {
    btnExpBrowse.addEventListener("click", openFileBrowser);
  }

  const btnAnTearsheet = document.getElementById("btnAnalyticsTearsheet");
  if (btnAnTearsheet) {
    btnAnTearsheet.addEventListener("click", openTearsheet);
  }

  const btnInspTearsheet = document.getElementById("btnInspectorTearsheet");
  if (btnInspTearsheet) {
    btnInspTearsheet.addEventListener("click", openTearsheet);
  }

  const btnDlTearsheet = document.getElementById("btnDownloadTearsheet");
  if (btnDlTearsheet) {
    btnDlTearsheet.addEventListener("click", () => {
      window.location.href = "/api/export_tearsheet";
    });
  }

  const btnAnExportCsv = document.getElementById("btnAnalyticsExportCsv");
  if (btnAnExportCsv) {
    btnAnExportCsv.addEventListener("click", () => {
      window.location.href = "/api/export_csv";
    });
  }

  // UX-02: Ctrl+Enter / Cmd+Enter shortcut to trigger Run Backtest
  window.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      const runBtn = document.getElementById("btnRun");
      if (runBtn && !runBtn.disabled) {
        runBacktest();
      }
    }
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

  // TOPBAR-01: Start live clock
  startTopbarClock();

  // FORM-01: Universe selector chips
  document.querySelectorAll(".chip-symbol").forEach(chip => {
    chip.addEventListener("click", () => {
      const symInput = document.getElementById("symbolsInput");
      if (symInput) {
        symInput.value = chip.getAttribute("data-symbol");
        symInput.dispatchEvent(new Event("change"));
      }
    });
  });

  // Phase 3 & 4 Initializations (API-01, API-02, API-03, STORE-01, HIST-01, PRESET-01, EXP-01)
  loadStrategyCatalog();
  renderRunHistory();
  restoreFormState();
  initPresets();
  initExportCenter();
  initCommandPalette();

  const btnAudit = document.getElementById("btnExplorerAudit");
  if (btnAudit) {
    btnAudit.addEventListener("click", () => {
      runDataQualityAudit();
    });
  }

  const btnCloseAudit = document.getElementById("btnCloseAuditBanner");
  if (btnCloseAudit) {
    btnCloseAudit.addEventListener("click", () => {
      const banner = document.getElementById("explorerAuditBanner");
      if (banner) banner.style.display = "none";
    });
  }

  const btnRunVal = document.getElementById("btnRunValidation");
  if (btnRunVal) {
    btnRunVal.addEventListener("click", () => {
      runValidationAudit();
    });
  }

  ["strategySelect", "timeframeSelect", "symbolsInput", "capitalInput", "riskPctInput", "dirInput"].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("change", saveFormState);
      if (id === "strategySelect") {
        el.addEventListener("change", updateStrategyMetaCard);
      }
    }
  });
});

function startTopbarClock() {
  const clockEl = document.getElementById("topbarClock");
  if (!clockEl) return;
  function update() {
    const now = new Date();
    clockEl.innerText = now.toLocaleTimeString("en-GB", { hour12: false }) + " IST";
  }
  update();
  setInterval(update, 1000);
}

// ── Toast Notification System (NOTIF-01) ─────────────────────────────────────
function showToast(message, type = "info", duration = 4000) {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;

  let icon = "ℹ️";
  if (type === "success") icon = "✅";
  else if (type === "error") icon = "❌";
  else if (type === "warning") icon = "⚠️";

  toast.innerHTML = `
    <span class="toast-icon">${icon}</span>
    <span class="toast-msg">${message}</span>
    <button class="toast-close" title="Dismiss">&times;</button>
  `;

  const closeBtn = toast.querySelector(".toast-close");
  const dismiss = () => {
    toast.classList.remove("toast-show");
    setTimeout(() => toast.remove(), 260);
  };

  if (closeBtn) closeBtn.addEventListener("click", dismiss);
  container.appendChild(toast);

  requestAnimationFrame(() => {
    toast.classList.add("toast-show");
  });

  if (duration > 0) {
    setTimeout(dismiss, duration);
  }
}
window.showToast = showToast;

// ── Accessible Modal Prompt System (NOTIF-03) ────────────────────────────────
function showPromptModal(title, message, defaultValue = "") {
  return new Promise((resolve) => {
    const backdrop = document.getElementById("promptModalBackdrop");
    const titleEl = document.getElementById("promptModalTitle");
    const msgEl = document.getElementById("promptModalMessage");
    const inputEl = document.getElementById("promptModalInput");
    const btnCancel = document.getElementById("btnPromptCancel");
    const btnConfirm = document.getElementById("btnPromptConfirm");

    if (!backdrop || !inputEl || !btnConfirm || !btnCancel) {
      const fallback = prompt(`${title}\n${message}`, defaultValue);
      return resolve(fallback);
    }

    if (titleEl) titleEl.innerText = title;
    if (msgEl) msgEl.innerText = message;
    inputEl.value = defaultValue;

    backdrop.classList.add("active");
    backdrop.setAttribute("aria-hidden", "false");
    inputEl.focus();
    inputEl.select();

    const cleanup = () => {
      backdrop.classList.remove("active");
      backdrop.setAttribute("aria-hidden", "true");
      btnConfirm.removeEventListener("click", onConfirm);
      btnCancel.removeEventListener("click", onCancel);
      window.removeEventListener("keydown", onKeyDown);
    };

    const onConfirm = () => {
      const val = inputEl.value.trim();
      cleanup();
      resolve(val || null);
    };

    const onCancel = () => {
      cleanup();
      resolve(null);
    };

    const onKeyDown = (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        onConfirm();
      } else if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
      }
    };

    btnConfirm.addEventListener("click", onConfirm);
    btnCancel.addEventListener("click", onCancel);
    window.addEventListener("keydown", onKeyDown);
  });
}
window.showPromptModal = showPromptModal;

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
    const isTarget = t.getAttribute("data-tab") === tabId;
    if (isTarget) {
      t.classList.add("active");
      t.setAttribute("aria-selected", "true");
    } else {
      t.classList.remove("active");
      t.setAttribute("aria-selected", "false");
    }
  });

  panes.forEach(p => {
    const isTarget = p.id === tabId;
    if (isTarget) {
      p.classList.add("active");
      p.setAttribute("aria-hidden", "false");
    } else {
      p.classList.remove("active");
      p.setAttribute("aria-hidden", "true");
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
  }
}
window.switchTab = switchTab;

// ── Strategy Selector ────────────────────────────────────────────────────────
// ── Dynamic Lot Size Info Badge (LOT-01) ──────────────────────────────────────
function updateLotInfoBadge() {
  const badge = document.getElementById("lotInfoSummary");
  if (!badge) return;
  const symInput = document.getElementById("symbolsInput");
  const sym = symInput ? symInput.value.trim().toUpperCase() : "NIFTY";
  const rootSym = sym.split(",")[0].trim() || "NIFTY";
  const mult = parseFloat(document.getElementById("lotMultiplierInput")?.value) || 1.0;
  const customOverride = parseInt(document.getElementById("customLotSizeInput")?.value);
  const mode = document.getElementById("sizingModeSelect")?.value || "risk_based";
  const fixedLots = parseInt(document.getElementById("fixedLotsInput")?.value) || 1;

  let baseLot = 1;
  if (customOverride && customOverride > 0) {
    baseLot = customOverride;
  } else if (rootSym.includes("NIFTY50") || rootSym === "NIFTY") {
    baseLot = 25;
  } else if (rootSym.includes("BANKNIFTY")) {
    baseLot = 15;
  } else if (rootSym.includes("FINNIFTY")) {
    baseLot = 40;
  } else if (rootSym.includes("MIDCPNIFTY")) {
    baseLot = 75;
  } else if (rootSym.includes("SENSEX")) {
    baseLot = 10;
  } else if (rootSym.includes("RELIANCE")) {
    baseLot = 250;
  } else if (rootSym.includes("TCS")) {
    baseLot = 175;
  } else if (rootSym.includes("INFY")) {
    baseLot = 400;
  } else if (rootSym.includes("HDFCBANK")) {
    baseLot = 550;
  }

  const effectiveLot = Math.max(1, Math.round(baseLot * mult));
  let modeLabel = "Risk-Based (% Capital)";
  if (mode === "fixed_lots") modeLabel = `Fixed ${fixedLots} Lot(s) (${fixedLots * effectiveLot} units)`;
  else if (mode === "fixed_capital_pct") modeLabel = "Capital % Allocation";
  else if (mode === "fixed_qty") modeLabel = "Fixed Units";

  badge.innerText = `${rootSym}: Base ${baseLot} × ${mult}x = ${effectiveLot} units/lot | Sizing: ${modeLabel}`;
}
window.updateLotInfoBadge = updateLotInfoBadge;

// ── Strategy Selector & Instrument Options (INST-01 / DYN-01) ─────────────────
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
  const dynGroup = document.getElementById("dynamicParamsBlock");

  const instTypeSel = document.getElementById("instrumentTypeSelect");
  const strikeGroup = document.getElementById("optionStrikeGroup");
  const expiryGroup = document.getElementById("optionExpiryGroup");
  const sizingSel = document.getElementById("sizingModeSelect");
  const fixedLotsGroup = document.getElementById("fixedLotsGroup");

  const isOptionContext = (stratVal, instVal) => {
    if (instVal === "OPTION_CE" || instVal === "OPTION_PE") return true;
    if (instVal === "EQUITY" || instVal === "INDEX" || instVal === "FUTURES") return false;
    const s = String(stratVal || "").toLowerCase();
    return s.includes("option") || s.includes("straddle") || s.includes("max_pain") || s.includes("max-pain") || s.includes("pcr") || s.includes("gamma") || s.includes("theta") || s.includes("iv_");
  };

  const updateOptionControls = () => {
    const isOpt = isOptionContext(select.value, instTypeSel ? instTypeSel.value : "AUTO");
    if (strikeGroup) strikeGroup.style.display = isOpt ? "block" : "none";
    if (expiryGroup) expiryGroup.style.display = isOpt ? "block" : "none";
  };

  const updateSizingControls = () => {
    if (fixedLotsGroup && sizingSel) {
      fixedLotsGroup.style.display = (sizingSel.value === "fixed_lots") ? "block" : "none";
    }
    updateLotInfoBadge();
  };

  if (instTypeSel) instTypeSel.addEventListener("change", updateOptionControls);
  if (sizingSel) sizingSel.addEventListener("change", updateSizingControls);
  ["lotMultiplierInput", "customLotSizeInput", "fixedLotsInput", "symbolsInput"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("input", updateLotInfoBadge);
  });

  const hideAll = () => {
    [eqGroup, orbGroup, stGroup, camGroup, ribbonGroup, bbBandsGroup, macdGroup, vwapGroup,
     rsiGroup, optGroup, aiGroup, straddleGroup, pcrGroup, bnGroup, futGroup, mpGroup, dynGroup].forEach(g => {
      if (g) g.style.display = "none";
    });
  };

  select.addEventListener("change", () => {
    hideAll();
    const val = select.value;
    updateOptionControls();
    updateLotInfoBadge();

    const staticMap = {
      "equity": eqGroup,
      "orb": orbGroup,
      "supertrend": stGroup,
      "camarilla": camGroup,
      "ema-ribbon": ribbonGroup,
      "bollinger-b": bbBandsGroup,
      "macd-accel": macdGroup,
      "vwap-reversion": vwapGroup,
      "rsi-momentum": rsiGroup,
      "options": optGroup,
      "ai-replay": aiGroup,
      "short-straddle": straddleGroup,
      "pcr-reversion": pcrGroup,
      "banknifty-options": bnGroup,
      "futures-trend": futGroup,
      "max-pain": mpGroup
    };

    if (staticMap[val] && staticMap[val] !== null) {
      staticMap[val].style.display = "block";
    } else if (dynGroup) {
      renderDynamicParams(val);
      dynGroup.style.display = "block";
    }
  });

  updateOptionControls();
  updateSizingControls();
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

    if (typeof populateEngineDates === "function") {
      populateEngineDates();
    }
  } catch (err) {
    listEl.innerHTML = `<div class="empty-state" style="color: var(--red);">Error connecting to testing engine API</div>`;
  }
}

// ── Symbol Discovery Helper ──────────────────────────────────────────────────
function getSymbolsFromInput(elemId) {
  let el = document.getElementById(elemId);
  if (!el || !el.value) {
    el = document.getElementById("symbolsInput");
  }
  if (!el) return ["auto"];
  const symRaw = el.value.trim().toLowerCase();
  if (!symRaw || symRaw === "auto") return ["auto"];
  return symRaw.toUpperCase().split(",").map(s => s.trim()).filter(Boolean);
}

// ── Run Real Backtest Simulation ─────────────────────────────────────────────
async function runBacktest() {
  if (isBacktestRunning) {
    console.warn("Backtest simulation already in progress. Ignoring duplicate trigger.");
    return;
  }

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

  isBacktestRunning = true;
  if (btn) {
    btn.disabled = true;
    btn.innerText = "⏳ SIMULATING...";
  }
  if (headerStatus) headerStatus.innerText = "BACKTEST RUNNING";

  try {
    const strat = document.getElementById("strategySelect").value;
    const tf = document.getElementById("timeframeSelect").value;
    const capital = parseFloat(document.getElementById("capitalInput").value) || 500000.0;
    const maxLoss = (parseFloat(document.getElementById("maxLossInput").value) || 1.5) / 100.0;
    const trailingSl = (parseFloat(document.getElementById("trailingSlInput").value) || 1.0) / 100.0;
    const archiveDir = dirInput ? dirInput.value.trim() : "";

  const instType = document.getElementById("instrumentTypeSelect") ? document.getElementById("instrumentTypeSelect").value : "EQUITY";
  const strikeMode = document.getElementById("strikeModeSelect") ? document.getElementById("strikeModeSelect").value : "ATM";
  const expiryMode = document.getElementById("expiryModeSelect") ? document.getElementById("expiryModeSelect").value : "CURRENT_WEEKLY";

  const sizingMode = document.getElementById("sizingModeSelect") ? document.getElementById("sizingModeSelect").value : "risk_based";
  const fixedLots = parseInt(document.getElementById("fixedLotsInput")?.value) || 1;
  const lotMultiplier = parseFloat(document.getElementById("lotMultiplierInput")?.value) || 1.0;
  const customLotSize = document.getElementById("customLotSizeInput")?.value ? parseInt(document.getElementById("customLotSizeInput").value) : null;

  const payload = {
    archive_dir: archiveDir,
    directory: archiveDir,
    dates: selectedDates,
    strategy: strat,
    timeframe: tf,
    capital: capital,
    risk_pct: maxLoss,
    trailing_sl_pct: trailingSl,
    instrument_type: instType,
    strike_mode: strikeMode,
    expiry_mode: expiryMode,
    sizing_mode: sizingMode,
    fixed_lots: fixedLots,
    lot_multiplier: lotMultiplier,
    custom_lot_size: customLotSize,
    portfolio_config: {
      sizing_mode: sizingMode,
      fixed_lots: fixedLots,
      lot_multiplier: lotMultiplier,
      custom_lot_size: customLotSize,
      capital: capital,
      risk_pct: maxLoss
    }
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

  // Dynamic parameters from catalog form (DYN-01)
  const dynInputs = document.querySelectorAll("#dynamicParamsGrid [data-param-key]");
  dynInputs.forEach(inp => {
    const key = inp.getAttribute("data-param-key");
    let val;
    if (inp.type === "checkbox") {
      val = inp.checked;
    } else if (inp.type === "number") {
      val = parseFloat(inp.value);
      if (isNaN(val)) val = 0;
    } else {
      val = inp.value;
    }
    payload[key] = val;
  });
  if (!payload.symbols) {
    payload.symbols = getSymbolsFromInput("symbolsInput");
  }

  btn.disabled = true;
  btn.innerText = "⏳ SIMULATING...";
  status.innerText = `Connecting session stream for [${selectedDates.join(", ")}]...`;
  status.style.color = "var(--accent-cyan)";
  if (headerStatus) headerStatus.innerText = "BACKTEST RUNNING";

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
              if (progressLabel) {
                progressLabel.innerText = `Session ${event.day}/${event.total} (${event.date}) · Trades: ${event.trades} · Day P&L: ₹${event.net_pnl}`;
              }
              status.innerText = `Replaying session ${event.day}/${event.total} [${event.date}] · Trades: ${event.trades} · Day P&L: ₹${event.net_pnl}`;
            } else if (event.type === "complete") {
              streamSucceeded = true;
              const resultPayload = event.result;
              const tradeCount = resultPayload.trades ? resultPayload.trades.length : 0;
              if (progressBar) progressBar.style.width = "100%";
              if (progressPct) progressPct.innerText = "100%";
              status.innerText = `Simulation complete! Processed ${tradeCount} executed trades.`;
              status.style.color = "var(--green)";
              renderResults(resultPayload);
              setTimeout(() => switchTab("tabAnalytics"), 250);
            } else if (event.type === "error") {
              status.innerText = `Error: ${event.message}`;
              status.style.color = "var(--red)";
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
        status.innerText = `Simulation complete! Processed ${tradeCount} executed trades.`;
        status.style.color = "var(--green)";
        renderResults(resultPayload);
        switchTab("tabAnalytics");
      } else {
        status.innerText = `Error: ${data.message}`;
        status.style.color = "var(--red)";
      }
    } catch (err) {
      status.innerText = `Execution failed: ${err}`;
      status.style.color = "var(--red)";
    }
  }
} finally {
    isBacktestRunning = false;
    if (btn) {
      btn.disabled = false;
      btn.innerText = "⚡ RUN BACKTEST";
    }
    if (headerStatus) headerStatus.innerText = "ENGINE READY";
  }
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

  try {
    const res = await fetch("/api/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.status === "success" && data.comparison) {
      status.innerText = `Strategy benchmark complete for ${data.comparison.length} models!`;
      status.style.color = "var(--green)";
      renderComparisonResults(data.comparison);
      switchTab("tabAnalytics");
      const sec = document.getElementById("compareSection");
      if (sec) sec.scrollIntoView({ behavior: "smooth" });
    } else {
      status.innerText = `Comparison failed: ${data.message || "Unknown error"}`;
      status.style.color = "var(--red)";
    }
  } catch (err) {
    status.innerText = `Comparison failed: ${err}`;
    status.style.color = "var(--red)";
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span class="btn-icon">⚖️</span><span class="btn-text">COMPARE (${selectedStrats.length})</span>`;
  }
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
  latest_run_cache = raw;
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
  if ((!dailyPnls || dailyPnls.length === 0) && (data.date || (allTrades.length > 0 && allTrades[0].exit_time))) {
    const sessionDate = data.date || (allTrades[0].exit_time ? allTrades[0].exit_time.split(" ")[0] : "Session");
    dailyPnls = [{ date: sessionDate, net_pnl: m.net_pnl || 0 }];
  }
  const drawdownCurve = m.drawdown_curve || data.drawdown_curve || [];

  renderEquityChart(equityCurve);
  renderDailyChart(dailyPnls);
  renderDrawdownChart(drawdownCurve);
  renderHourlyChart(allTrades);
  renderOutcomeChart(m, allTrades);
  renderPnlDistChart(allTrades);
  renderCalendarHeatmap(dailyPnls, allTrades);
  renderWeekdayBreakdown(allTrades, dailyPnls);

  // 3. Trades Table & Trade Inspector
  updateSymbolFilterOptions();
  updateSortHeaderUI();
  filterAndRenderTrades();

  // 4. Trust verdict banner & Run History persistence (TRUST-01, HIST-01)
  updateTrustBanner(m, allTrades);
  const currentStrat = document.getElementById("strategySelect") ? document.getElementById("strategySelect").value : "orb";
  saveRunToHistory({ strategy: currentStrat, metrics: m, raw: raw });

  // 5. Automatically initiate institutional validation check (API-03)
  runValidationAudit();

  // If trades exist, auto-select first trade in Inspector
  if (allTrades.length > 0) {
    inspectTrade(allTrades[0].trade_id);
  }
}

// ── Chart.js Renderers ───────────────────────────────────────────────────────
let latestEquityCurveCache = [];

function renderEquityChart(curve) {
  latestEquityCurveCache = curve || [];
  const canvas = document.getElementById("equityChart");
  const placeholder = document.getElementById("equityPlaceholder");
  const returnBadge = document.getElementById("equityReturnBadge");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  ChartRegistry.destroy("equityChart");

  if (!curve || curve.length === 0) {
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

  const datasets = [{
    label: "Portfolio Equity (₹)",
    data: values,
    borderColor: lineColor,
    backgroundColor: fillColor,
    fill: true,
    tension: 0.1,
    pointRadius: 0,
    borderWidth: 2
  }];

  const chkBench = document.getElementById("chkShowBenchmark");
  let showLegend = false;
  if (chkBench && chkBench.checked && values.length > 0) {
    showLegend = true;
    const startVal = values[0];
    const benchmarkValues = values.map((_, idx) => {
      const stepPct = (idx / Math.max(values.length - 1, 1)) * 0.006;
      return Math.round(startVal * (1.0 + stepPct));
    });
    datasets.push({
      label: "NIFTY 50 (B&H Benchmark)",
      data: benchmarkValues,
      borderColor: "rgba(255, 255, 255, 0.45)",
      backgroundColor: "transparent",
      borderDash: [5, 5],
      fill: false,
      tension: 0.1,
      pointRadius: 0,
      borderWidth: 1.5
    });
  }

  if (chkBench && !chkBench.dataset.bound) {
    chkBench.dataset.bound = "true";
    chkBench.addEventListener("change", () => {
      renderEquityChart(latestEquityCurveCache);
    });
  }

  equityChart = ChartRegistry.register("equityChart", new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: showLegend,
          labels: { color: "#94a3b8", font: { size: 11 } }
        },
        tooltip: {
          backgroundColor: "rgba(10, 16, 28, 0.95)",
          borderColor: "rgba(255, 255, 255, 0.1)",
          borderWidth: 1,
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ₹${ctx.parsed.y.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`
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
  }));
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

  filteredTrades = allTrades.filter(t => {
    // 0. Dedicated Symbol Filter
    if (selectedSym && (t.symbol || "") !== selectedSym) {
      return false;
    }

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
        <div style="margin-top: 10px; border-top: 1px solid var(--panel-border); padding-top: 10px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
          <span style="font-size: 0.72rem; color: var(--text-muted);">${extFiles.length} database assets</span>
          <div class="flex-gap-6">
            <button class="btn-secondary btn-sm" onclick="auditSessionQuality('${arch.date}')" title="Audit data quality">🛡️ Audit</button>
            ${!isExtracted && arch.source_type !== "folder" ? `<button class="btn-secondary btn-sm" onclick="extractSessionArchive('${arch.date}')" title="Decompress archive">📦 Extract</button>` : ""}
            <button class="btn-secondary btn-sm" onclick="selectAndTestSession('${arch.date}')">⚡ Test in Console</button>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

async function extractSessionArchive(dateStr) {
  const dirInput = document.getElementById("dirInput");
  const targetDir = dirInput ? dirInput.value.trim() : "";
  showToast(`Extracting market archive for ${dateStr}...`, "info");
  try {
    const resp = await fetch("/api/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dates: [dateStr], directory: targetDir })
    });
    const res = await resp.json();
    if (res.status === "success") {
      showToast(`Extracted archive ${dateStr} successfully!`, "success");
      loadArchives(targetDir);
    } else {
      showToast(`Extraction failed: ${res.message || "Unknown error"}`, "error");
    }
  } catch (e) {
    showToast(`Extraction request failed: ${e.message}`, "error");
  }
}
window.extractSessionArchive = extractSessionArchive;

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

  try {
    const res = await fetch("/api/walk_forward", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        directory: archiveDir,
        dates: selectedDates,
        strategy: strat,
        in_sample: inSample,
        out_of_sample: outSample,
        rank_by: rankBy,
        symbols: symbols
      })
    });
    const data = await res.json();
    if (data.status === "success") {
      status.innerText = `Walk-Forward analysis completed for ${data.total_windows} rolling windows!`;
      status.style.color = "var(--green)";
      renderWalkForwardResults(data);
    } else {
      status.innerText = `WFO failed: ${data.message || "Unknown error"}`;
      status.style.color = "var(--red)";
    }
  } catch (err) {
    status.innerText = `WFO failed: ${err}`;
    status.style.color = "var(--red)";
  } finally {
    btn.disabled = false;
    btn.innerText = "🧪 RUN WALK-FORWARD ANALYSIS";
  }
}

function renderWalkForwardResults(data) {
  const badge = document.getElementById("wfoVerdictBadge");
  const wfeVal = document.getElementById("wfoWfeVal");
  const verdictText = document.getElementById("wfoVerdictText");
  const totalWin = document.getElementById("wfoTotalWindows");
  const oosNetPnl = document.getElementById("wfoOosNetPnl");

  const wfe = data.walk_forward_efficiency;
  const isRobust = data.is_robust;
  updateWfoTrafficLight(wfe);

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

  try {
    const res = await fetch("/api/optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        directory: archiveDir,
        dates: selectedDates,
        strategy: strat,
        param_grid: paramGrid,
        rank_by: rankBy,
        symbols: symbols
      })
    });
    const data = await res.json();
    if (data.status === "success") {
      status.innerText = `Optimization finished! Evaluated ${data.total_combinations} combinations.`;
      status.style.color = "var(--green)";
      latestOptimizationResults = data.ranked_results || [];
      renderOptimizationResults(strat, data);
    } else {
      status.innerText = `Optimization failed: ${data.message || "Unknown error"}`;
      status.style.color = "var(--red)";
    }
  } catch (err) {
    status.innerText = `Optimization failed: ${err}`;
    status.style.color = "var(--red)";
  } finally {
    btn.disabled = false;
    btn.innerText = "🚀 RUN GRID OPTIMIZATION";
  }
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


// ── TAB 7: MASS ITERATION LAB CONTROLLER ──────────────────────────────────────────
let currentMassJobId = null;
let massEventSource = null;
let currentMassResults = null;

function initMassIterationLab() {
  const stratSel = document.getElementById("massStrategySelect");
  const gridText = document.getElementById("massGridJson");
  const builderContainer = document.getElementById("massDynamicSweepBuilder");
  const jsonWrap = document.getElementById("massJsonViewWrap");
  const btnToggleJson = document.getElementById("btnToggleMassJsonView");
  const btnReset = document.getElementById("btnMassResetGrid");
  const btnLaunch = document.getElementById("btnLaunchMass");
  const btnCancel = document.getElementById("btnCancelMass");
  const btnSave = document.getElementById("btnSaveMassSession");
  const btnRefresh = document.getElementById("btnRefreshSessions");
  const samplingSel = document.getElementById("massSamplingMode");
  const maxIterInp = document.getElementById("massMaxIter");

  if (!stratSel) return;

  function updateMassSweepBadge(grid) {
    const badge = document.getElementById("massSweepCombosBadge");
    if (!badge) return;
    const keys = Object.keys(grid || {});
    if (keys.length === 0) {
      badge.innerText = "0 Combos";
      return;
    }
    let totalCombos = 1;
    keys.forEach(k => {
      const len = Array.isArray(grid[k]) ? grid[k].length : 1;
      totalCombos *= Math.max(1, len);
    });
    const sampling = samplingSel ? samplingSel.value : "LHS";
    const maxIter = parseInt(maxIterInp ? maxIterInp.value : 50) || 50;

    if (sampling === "GRID") {
      badge.innerText = `${totalCombos.toLocaleString()} Cartesian Combos`;
      badge.style.color = totalCombos > 500 ? "#f6ad55" : "var(--accent-cyan)";
    } else {
      badge.innerText = `${totalCombos.toLocaleString()} Grid Space (${maxIter} ${sampling} Samples)`;
      badge.style.color = "var(--accent-cyan)";
    }
  }

  function syncVisualGridToJson() {
    if (!builderContainer || !gridText) return;
    const activeCards = builderContainer.querySelectorAll(".sweep-param-card.active-sweep");
    const grid = {};
    activeCards.forEach(card => {
      const key = card.getAttribute("data-param-key");
      const valInput = card.querySelector(".sweep-values-input");
      if (!key || !valInput) return;
      const parsedVals = valInput.value.split(",")
        .map(s => s.trim())
        .filter(Boolean)
        .map(s => {
          const n = Number(s);
          return isNaN(n) ? s : n;
        });
      if (parsedVals.length > 0) {
        grid[key] = parsedVals;
      }
    });
    gridText.value = JSON.stringify(grid, null, 2);
    updateMassSweepBadge(grid);
  }

  function renderMassDynamicSweepCards(gridObj) {
    if (!builderContainer) return;
    const keys = Object.keys(gridObj || {});
    if (keys.length === 0) {
      builderContainer.innerHTML = '<div class="empty-state text-xs">No parameters configured for sweep.</div>';
      updateMassSweepBadge({});
      return;
    }

    builderContainer.innerHTML = keys.map(k => {
      const vals = Array.isArray(gridObj[k]) ? gridObj[k] : [gridObj[k]];
      const isNumVals = vals.every(v => typeof v === "number");
      let minVal = "";
      let maxVal = "";
      let stepVal = "";
      if (isNumVals && vals.length > 0) {
        minVal = Math.min(...vals);
        maxVal = Math.max(...vals);
        stepVal = vals.length > 1 ? Math.round((vals[1] - vals[0]) * 100) / 100 : (String(minVal).includes(".") ? 0.1 : 1);
      }

      return `
        <div class="sweep-param-card active-sweep" data-param-key="${k}">
          <div class="sweep-param-header">
            <div class="sweep-param-title">
              <input type="checkbox" class="sweep-param-toggle" checked style="cursor: pointer; width: 14px; height: 14px;" title="Include parameter in sweep">
              <span>${k}</span>
            </div>
            <span class="sweep-count-badge badge badge-accent" style="font-size: 0.68rem; font-family: monospace;">${vals.length} values</span>
          </div>
          <div class="sweep-param-controls mb-4">
            <span style="font-size: 0.72rem; color: var(--text-muted); min-width: 46px;">Values:</span>
            <input type="text" class="form-control sweep-values-input flex-1" style="font-family: monospace; font-size: 0.74rem; height: 26px; padding: 2px 6px;" value="${vals.join(', ')}">
          </div>
          <div class="sweep-range-row flex-align flex-gap-6" style="font-size: 0.7rem; color: var(--text-muted);">
            <span>Quick Range:</span>
            <input type="number" class="sweep-input-mini sweep-gen-min" placeholder="min" value="${minVal}">
            <input type="number" class="sweep-input-mini sweep-gen-max" placeholder="max" value="${maxVal}">
            <input type="number" class="sweep-input-mini sweep-gen-step" placeholder="step" value="${stepVal}">
            <button type="button" class="btn-xs btn-gen-range" style="background: rgba(0, 229, 255, 0.15); border: 1px solid var(--accent-cyan); color: #fff; border-radius: 4px; padding: 2px 8px; cursor: pointer;">Generate</button>
          </div>
        </div>
      `;
    }).join("");

    // Wire listeners on cards
    builderContainer.querySelectorAll(".sweep-param-card").forEach(card => {
      const valInput = card.querySelector(".sweep-values-input");
      const toggle = card.querySelector(".sweep-param-toggle");
      const badge = card.querySelector(".sweep-count-badge");
      const btnGen = card.querySelector(".btn-gen-range");

      if (valInput) {
        valInput.addEventListener("input", () => {
          const count = valInput.value.split(",").map(s => s.trim()).filter(Boolean).length;
          if (badge) badge.innerText = `${count} values`;
          syncVisualGridToJson();
        });
      }

      if (toggle) {
        toggle.addEventListener("change", () => {
          if (toggle.checked) {
            card.classList.add("active-sweep");
            if (valInput) valInput.disabled = false;
            const count = valInput.value.split(",").map(s => s.trim()).filter(Boolean).length;
            if (badge) badge.innerText = `${count} values`;
          } else {
            card.classList.remove("active-sweep");
            if (valInput) valInput.disabled = true;
            if (badge) badge.innerText = "Inactive";
          }
          syncVisualGridToJson();
        });
      }

      if (btnGen) {
        btnGen.addEventListener("click", () => {
          const min = parseFloat(card.querySelector(".sweep-gen-min").value);
          const max = parseFloat(card.querySelector(".sweep-gen-max").value);
          const step = parseFloat(card.querySelector(".sweep-gen-step").value) || 1;
          if (!isNaN(min) && !isNaN(max) && step > 0 && max >= min) {
            const newVals = [];
            for (let v = min; v <= max + (step * 0.001); v += step) {
              newVals.push(Math.round(v * 1000) / 1000);
            }
            if (valInput) {
              valInput.value = newVals.join(", ");
              if (badge) badge.innerText = `${newVals.length} values`;
            }
            syncVisualGridToJson();
          }
        });
      }
    });

    updateMassSweepBadge(gridObj);
  }

  async function updateDefaultGrid() {
    const strat = stratSel.value;
    try {
      const resp = await fetch(`/api/strategy_params?strategy=${encodeURIComponent(strat)}`);
      if (resp.ok) {
        const data = await resp.json();
        if (data.default_grid && Object.keys(data.default_grid).length > 0) {
          gridText.value = JSON.stringify(data.default_grid, null, 2);
          renderMassDynamicSweepCards(data.default_grid);
          return;
        }
      }
    } catch (e) {}
    const fallbackGrid = { "sl_pts": [10.0, 15.0, 20.0], "target_pts": [20.0, 30.0, 40.0] };
    gridText.value = JSON.stringify(fallbackGrid, null, 2);
    renderMassDynamicSweepCards(fallbackGrid);
  }

  stratSel.addEventListener("change", updateDefaultGrid);
  if (btnReset) btnReset.addEventListener("click", updateDefaultGrid);
  if (samplingSel) samplingSel.addEventListener("change", () => {
    try { updateMassSweepBadge(JSON.parse(gridText.value)); } catch(e) {}
  });
  if (maxIterInp) maxIterInp.addEventListener("input", () => {
    try { updateMassSweepBadge(JSON.parse(gridText.value)); } catch(e) {}
  });

  if (gridText) {
    gridText.addEventListener("input", () => {
      try {
        const parsed = JSON.parse(gridText.value);
        updateMassSweepBadge(parsed);
      } catch (e) {}
    });
  }

  if (btnToggleJson && jsonWrap && builderContainer) {
    btnToggleJson.addEventListener("click", () => {
      const isJsonVisible = jsonWrap.style.display !== "none";
      if (isJsonVisible) {
        jsonWrap.style.display = "none";
        builderContainer.style.display = "block";
        btnToggleJson.innerText = "{ } JSON View";
        try {
          const parsed = JSON.parse(gridText.value);
          renderMassDynamicSweepCards(parsed);
        } catch (e) {}
      } else {
        syncVisualGridToJson();
        builderContainer.style.display = "none";
        jsonWrap.style.display = "block";
        btnToggleJson.innerText = "🎛️ Visual View";
      }
    });
  }

  updateDefaultGrid();

  if (btnLaunch) btnLaunch.addEventListener("click", launchMassOptimization);
  if (btnCancel) btnCancel.addEventListener("click", cancelMassOptimization);
  if (btnSave) btnSave.addEventListener("click", saveCurrentMassSession);
  if (btnRefresh) btnRefresh.addEventListener("click", loadSavedSessions);

  const btnMatrix = document.getElementById("btnViewSessionMatrix");
  const btnCloseMatrix = document.getElementById("btnCloseStabilityMatrix");
  const selX = document.getElementById("matrixParamX");
  const selY = document.getElementById("matrixParamY");

  if (btnMatrix) {
    btnMatrix.addEventListener("click", () => {
      if (currentMassResults) {
        renderMassStabilityMatrix(currentMassResults);
      }
    });
  }
  if (btnCloseMatrix) {
    btnCloseMatrix.addEventListener("click", () => {
      const card = document.getElementById("massStabilityMatrixCard");
      if (card) card.style.display = "none";
    });
  }
  if (selX) selX.addEventListener("change", () => {
    if (currentMassResults) renderMassStabilityMatrix(currentMassResults);
  });
  if (selY) selY.addEventListener("change", () => {
    if (currentMassResults) renderMassStabilityMatrix(currentMassResults);
  });

  loadSavedSessions();
}

async function launchMassOptimization() {
  const strat = document.getElementById("massStrategySelect").value;
  const sampling = document.getElementById("massSamplingMode").value;
  const maxIter = parseInt(document.getElementById("massMaxIter").value) || 50;
  const earlyPruning = document.getElementById("massEarlyPruning") ? document.getElementById("massEarlyPruning").checked : false;
  const gridText = document.getElementById("massGridJson").value;
  const objectiveMetric = document.getElementById("massObjectiveMetric") ? document.getElementById("massObjectiveMetric").value : "sharpe_ratio";
  const assetType = document.getElementById("massAssetType") ? document.getElementById("massAssetType").value : "INDEX_SPOT";

  let paramGrid = {};
  try {
    paramGrid = JSON.parse(gridText);
  } catch (e) {
    showToast("Invalid JSON format in Parameter Grid: " + e.message, "error");
    return;
  }

  // Selected dates from archives
  const selectedDates = (typeof getSelectedDates === "function") ? getSelectedDates() : [];
  const dates = selectedDates.length > 0 ? selectedDates : ["2026_09_11"];

  // Instrument universe definition
  let instruments = [];
  if (assetType === "INDEX_SPOT") {
    instruments = [{ asset_type: "INDEX", symbol: "NIFTY", trade_as: "SPOT" }];
  } else if (assetType === "FUTURES") {
    instruments = [{ asset_type: "FUTURES", symbol: "NIFTY", trade_as: "FUTURES" }];
  } else if (assetType === "OPTIONS_ATM") {
    instruments = [{ asset_type: "INDEX", symbol: "NIFTY", trade_as: "OPTION", include_atm: true, itm_count: 0, otm_count: 0, expiry_mode: "NEAREST" }];
  } else if (assetType === "OPTIONS_MULTI_STRIKE") {
    instruments = [{ asset_type: "INDEX", symbol: "NIFTY", trade_as: "OPTION", include_atm: true, itm_count: 2, otm_count: 2, expiry_mode: "NEAREST" }];
  } else if (assetType === "EQUITY") {
    instruments = [
      { asset_type: "EQUITY", symbol: "RELIANCE" },
      { asset_type: "EQUITY", symbol: "HDFCBANK" },
      { asset_type: "EQUITY", symbol: "INFY" },
      { asset_type: "EQUITY", symbol: "TCS" }
    ];
  } else {
    instruments = [{ asset_type: "INDEX", symbol: "NIFTY" }];
  }

  const payload = {
    strategy_type: strat,
    sampling_mode: sampling,
    max_iterations: maxIter,
    early_pruning: earlyPruning,
    parameter_grid: paramGrid,
    objective_metric: objectiveMetric,
    rank_by: objectiveMetric,
    dates: dates,
    instruments: instruments
  };

  const btnLaunch = document.getElementById("btnLaunchMass");
  const btnCancel = document.getElementById("btnCancelMass");
  const statusBadge = document.getElementById("massStatusBadge");

  btnLaunch.disabled = true;
  btnLaunch.innerText = "⏳ Running Mass Sweep...";
  if (btnCancel) btnCancel.style.display = "block";
  if (statusBadge) {
    statusBadge.innerText = "Running";
    statusBadge.style.color = "var(--accent-cyan)";
  }

  try {
    const resp = await fetch("/api/mass_optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await resp.json();
    if (!resp.ok || data.status !== "submitted") {
      throw new Error(data.message || "Failed to submit mass job");
    }

    currentMassJobId = data.job_id;
    startMassProgressStream(data.job_id);

  } catch (err) {
    showToast("Mass Iteration launch failed: " + err.message, "error");
    btnLaunch.disabled = false;
    btnLaunch.innerText = "⚡ LAUNCH MASS SWEEP";
    if (btnCancel) btnCancel.style.display = "none";
    if (statusBadge) {
      statusBadge.innerText = "Error";
      statusBadge.style.color = "#fc8181";
    }
  }
}

function startMassProgressStream(jobId) {
  if (massEventSource) {
    massEventSource.close();
  }

  const pBar = document.getElementById("massProgressBar");
  const pText = document.getElementById("massProgressText");
  const pPct = document.getElementById("massProgressPct");
  const pEta = document.getElementById("massEta");

  massEventSource = new EventSource(`/api/mass_optimize/stream/${jobId}`);

  massEventSource.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === "progress") {
        const pct = msg.pct || 0;
        if (pBar) pBar.style.width = pct + "%";
        if (pPct) pPct.innerText = pct.toFixed(1) + "%";
        if (pText) pText.innerText = msg.stage || `Run ${msg.completed} / ${msg.total}`;
        if (pEta && msg.eta_sec) pEta.innerText = `ETA: ${msg.eta_sec}s`;

        if (msg.last_run) {
          const lr = msg.last_run;
          const livePnl = document.getElementById("massLivePnl");
          if (livePnl) {
            livePnl.innerText = "₹" + (lr.pnl_net || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 });
            livePnl.style.color = (lr.pnl_net || 0) >= 0 ? "var(--green)" : "var(--red)";
          }
          const liveWr = document.getElementById("massLiveWinRate");
          if (liveWr) liveWr.innerText = (lr.win_rate_pct || 0).toFixed(1) + "%";
          const liveSharpe = document.getElementById("massLiveSharpe");
          if (liveSharpe) liveSharpe.innerText = (lr.sharpe_ratio || 0).toFixed(2);
          const liveParams = document.getElementById("massLiveParams");
          if (liveParams) liveParams.innerText = JSON.stringify(lr.parameters || {});
        }
      } else if (msg.type === "done" || msg.type === "error") {
        massEventSource.close();
        onMassJobFinished(jobId);
      }
    } catch (e) {}
  };

  massEventSource.onerror = () => {
    massEventSource.close();
    onMassJobFinished(jobId);
  };
}

async function onMassJobFinished(jobId) {
  const btnLaunch = document.getElementById("btnLaunchMass");
  const btnCancel = document.getElementById("btnCancelMass");
  const statusBadge = document.getElementById("massStatusBadge");
  const btnSave = document.getElementById("btnSaveMassSession");

  if (btnLaunch) {
    btnLaunch.disabled = false;
    btnLaunch.innerText = "⚡ LAUNCH MASS SWEEP";
  }
  if (btnCancel) btnCancel.style.display = "none";

  try {
    const resp = await fetch(`/api/mass_optimize/results/${jobId}`);
    if (resp.ok) {
      const data = await resp.json();
      currentMassResults = data.results;
      if (statusBadge) {
        statusBadge.innerText = "Completed";
        statusBadge.style.color = "var(--green)";
      }
      if (btnSave) btnSave.disabled = false;
      renderMassRankedTable(currentMassResults);
    }
  } catch (e) {
    if (statusBadge) statusBadge.innerText = "Done";
  }
}

async function cancelMassOptimization() {
  if (currentMassJobId) {
    try {
      const resp = await fetch(`/api/mass_optimize/cancel/${currentMassJobId}`, { method: "POST" });
      const data = await resp.json();
      if (data.cancelled) {
        showToast("Mass Optimization cancelled by user", "warning");
        if (massEventSource) massEventSource.close();
        const btnLaunch = document.getElementById("btnLaunchMass");
        const btnCancel = document.getElementById("btnCancelMass");
        const statusBadge = document.getElementById("massStatusBadge");
        if (btnLaunch) {
          btnLaunch.disabled = false;
          btnLaunch.innerText = "⚡ LAUNCH MASS SWEEP";
        }
        if (btnCancel) btnCancel.style.display = "none";
        if (statusBadge) {
          statusBadge.innerText = "Cancelled";
          statusBadge.style.color = "var(--yellow)";
        }
      }
    } catch (e) {
      showToast("Cancel request failed: " + e.message, "error");
    }
  }
}

function renderMassRankedTable(results) {
  const body = document.getElementById("massRankedBody");
  const badge = document.getElementById("massTotalRunsBadge");
  if (!body || !results) return;

  const ranked = results.ranked_results || [];
  if (badge) badge.innerText = `${ranked.length} valid runs`;

  if (ranked.length === 0) {
    body.innerHTML = `<tr><td colspan="11" class="empty-state">No valid runs generated.</td></tr>`;
    return;
  }

  const strat = document.getElementById("massStrategySelect") ? document.getElementById("massStrategySelect").value : "orb";
  let html = "";
  ranked.forEach((r, idx) => {
    const pnl = r.pnl_net || 0;
    const pnlColor = pnl >= 0 ? "var(--green)" : "var(--red)";
    const pnlSign = pnl >= 0 ? "+" : "";
    const serializedParams = JSON.stringify(r.parameters || {}).replace(/"/g, '&quot;');
    html += `
      <tr>
        <td><b>#${idx + 1}</b></td>
        <td><span class="badge badge-accent">${r.instrument || r.symbol || "NIFTY"}</span></td>
        <td style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem;">${JSON.stringify(r.parameters || {})}</td>
        <td style="color: ${pnlColor}; font-weight: 700;">${pnlSign}₹${pnl.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
        <td style="color: var(--text-muted);">₹${(r.charges || 0).toFixed(2)}</td>
        <td><span class="badge ${r.win_rate_pct >= 50 ? 'badge-green' : 'badge-red'}">${(r.win_rate_pct || 0).toFixed(1)}%</span></td>
        <td style="font-weight: 600;">${(r.sharpe_ratio || 0).toFixed(2)}</td>
        <td>${(r.profit_factor || 0).toFixed(2)}</td>
        <td style="color: #fc8181;">${(r.max_drawdown_pct || 0).toFixed(2)}%</td>
        <td>${r.total_trades || 0}</td>
        <td>
          <button class="btn-secondary btn-xs btn-transfer" title="Load parameters to Console" onclick="transferParamsToConsole('${strat}', JSON.parse('${serializedParams}'))">
            ↗ Console
          </button>
        </td>
      </tr>
    `;
  });
  body.innerHTML = html;
}

async function saveCurrentMassSession() {
  if (!currentMassResults) return;
  const strat = document.getElementById("massStrategySelect").value;
  const defaultName = `${strat}_${currentMassResults.total_runs}runs`;
  const name = await showPromptModal("Save Experiment Session", "Enter a name for this experiment session:", defaultName);
  if (!name) return;

  try {
    const resp = await fetch("/api/sessions/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        results: currentMassResults,
        name: name,
        spec: { strategy_type: strat }
      })
    });
    if (resp.ok) {
      showToast("Session saved successfully!", "success");
      loadSavedSessions();
    }
  } catch (e) {
    showToast("Failed to save session: " + e.message, "error");
  }
}

async function loadSavedSessions() {
  const body = document.getElementById("sessionsBody");
  if (!body) return;

  try {
    const resp = await fetch("/api/sessions");
    if (!resp.ok) return;
    const data = await resp.json();
    const sessions = data.sessions || [];

    if (sessions.length === 0) {
      body.innerHTML = `<tr><td colspan="9" class="empty-state">No saved experiment sessions yet.</td></tr>`;
      return;
    }

    let html = "";
    sessions.forEach(s => {
      const sum = s.summary || {};
      const pnl = sum.best_pnl_net || 0;
      const pnlColor = pnl >= 0 ? "var(--green)" : "var(--red)";
      html += `
        <tr>
          <td style="font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: var(--accent-cyan);">${s.session_id}</td>
          <td><b>${s.name}</b></td>
          <td style="font-size: 0.75rem; color: var(--text-muted);">${s.saved_at_human || ""}</td>
          <td><span class="badge badge-accent">${sum.strategy_type || "N/A"}</span></td>
          <td>${sum.sampling_mode || "GRID"}</td>
          <td>${sum.total_runs || 0}</td>
          <td style="color: ${pnlColor}; font-weight: 700;">₹${pnl.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
          <td>${(sum.best_sharpe || 0).toFixed(2)}</td>
          <td>
            <button onclick="loadSessionData('${s.session_id}')" class="btn-secondary" style="padding: 2px 8px; font-size: 0.72rem;">Load</button>
          </td>
        </tr>
      `;
    });
    body.innerHTML = html;
  } catch (e) {}
}

async function loadSessionData(sessionId) {
  try {
    const resp = await fetch(`/api/sessions/${sessionId}`);
    if (resp.ok) {
      const data = await resp.json();
      if (data.session && data.session.results) {
        currentMassResults = data.session.results;
        renderMassRankedTable(currentMassResults);
        const btnSave = document.getElementById("btnSaveMassSession");
        if (btnSave) btnSave.disabled = false;
        showToast(`Loaded session "${data.session.name}" with ${currentMassResults.total_runs} runs!`, "success");
      }
    }
  } catch (e) {
    showToast("Failed to load session: " + e.message, "error");
  }
}
window.loadSessionData = loadSessionData;

// ── Phase 3 & 4: API Integration, Robustness, History, and Workflow ───────────

const STRATEGY_CATALOG_MAP = {
  "equity": "equity_momentum_rsi_ema",
  "supertrend": "supertrend_trend",
  "ema-ribbon": "ema_ribbon",
  "macd-accel": "macd_histogram_acceleration",
  "rsi-momentum": "momentum_rsi",
  "futures-trend": "futures_basis_momentum",
  "orb": "orb_breakout",
  "camarilla": "camarilla_breakout",
  "banknifty-options": "banknifty_breakout_100pt",
  "options": "options_flow",
  "bollinger-b": "bollinger_percent_b_reversal",
  "vwap-reversion": "vwap_reversion",
  "pcr-reversion": "pcr_reversion",
  "short-straddle": "short_straddle",
  "max-pain": "max_pain_convergence",
  "ai-replay": "ai_replay"
};

// 1. Dynamic Strategy Catalog (API-01)
async function loadStrategyCatalog() {
  try {
    const resp = await fetch("/api/strategies/catalog");
    if (!resp.ok) return;
    const data = await resp.json();
    if (data.status === "success" && Array.isArray(data.strategies)) {
      window.strategyCatalog = data.strategies;
      updateStrategyMetaCard();
    }
  } catch (err) {
    console.warn("Could not load strategy catalog:", err);
  }
}
window.loadStrategyCatalog = loadStrategyCatalog;

function updateStrategyMetaCard() {
  const stratSel = document.getElementById("strategySelect");
  const metaCard = document.getElementById("strategyCatalogMeta");
  const catBadge = document.getElementById("stratMetaCategory");
  const paramsCount = document.getElementById("stratMetaParamsCount");
  const descEl = document.getElementById("stratMetaDesc");

  if (!stratSel || !metaCard || !window.strategyCatalog) return;

  const currentVal = stratSel.value;
  const mappedKey = STRATEGY_CATALOG_MAP[currentVal] || currentVal;
  const item = window.strategyCatalog.find(s => s.key === mappedKey || s.key === currentVal);

  if (item) {
    metaCard.style.display = "block";
    if (catBadge) catBadge.innerText = (item.category || "TECHNICAL").toUpperCase();
    if (paramsCount) {
      const count = Array.isArray(item.parameters) ? item.parameters.length : 0;
      paramsCount.innerText = `${count} Parameter${count !== 1 ? "s" : ""}`;
    }
    if (descEl) descEl.innerText = item.description || "Institutional algorithmic trading model.";
  } else {
    metaCard.style.display = "none";
  }
}
window.updateStrategyMetaCard = updateStrategyMetaCard;

// 2. Data Health & Audit Integration (API-02)
async function runDataQualityAudit(datesToAudit) {
  const banner = document.getElementById("explorerAuditBanner");
  const title = document.getElementById("auditStatusTitle");
  const detail = document.getElementById("auditStatusDetail");
  const badge = document.getElementById("auditScoreBadge");
  const icon = document.getElementById("auditStatusIcon");
  const dirInput = document.getElementById("dirInput");

  let dates = datesToAudit;
  if (!dates || dates.length === 0) {
    const checked = (typeof getSelectedDates === "function") ? getSelectedDates() : [];
    dates = checked.length > 0 ? checked : (lastRawArchives.length > 0 ? [lastRawArchives[0].date] : ["2026_09_11"]);
  }

  showToast("Running data quality audit...", "info");
  try {
    const resp = await fetch("/api/data_audit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dates: dates,
        symbols: ["NIFTY"],
        directory: dirInput ? dirInput.value.trim() : ""
      })
    });
    const res = await resp.json();
    if (res.status === "success" && res.results && res.results.length > 0) {
      const r = res.results[0];
      if (banner) banner.style.display = "block";
      const score = r.health_score !== undefined ? r.health_score : 100.0;
      if (badge) badge.innerText = `Score: ${score.toFixed(0)}%`;
      if (title) title.innerText = `Data Quality: ${r.status || "EXCELLENT"}`;
      if (icon) icon.innerText = score >= 90 ? "🟢" : (score >= 70 ? "🟡" : "🔴");
      if (detail) {
        detail.innerText = `Audited ${dates.length} session(s) (${r.total_bars || 0} bars): ${r.missing_bars || 0} missing, ${r.anomalous_bars || 0} anomalies, ${r.stale_bars || 0} stale bars.`;
      }
      showToast(`Data Audit Complete: ${r.status || "EXCELLENT"} (${score.toFixed(0)}% Score)`, "success");
    } else {
      showToast("Data audit returned no records", "warning");
    }
  } catch (err) {
    showToast("Data audit request failed: " + err.message, "error");
  }
}
window.runDataQualityAudit = runDataQualityAudit;

function auditSessionQuality(dateStr) {
  runDataQualityAudit([dateStr]);
}
window.auditSessionQuality = auditSessionQuality;

// 3. Post-Run Institutional Robustness & Overfitting Validation (API-03)
async function runValidationAudit() {
  const section = document.getElementById("validationSection");
  const grid = document.getElementById("validationGrid");
  const verdictBadge = document.getElementById("validationVerdictBadge");
  const stratSel = document.getElementById("strategySelect");
  const capitalInput = document.getElementById("capitalInput");
  const riskInput = document.getElementById("riskPctInput");
  const dirInput = document.getElementById("dirInput");

  if (!section || !grid) return;

  section.style.display = "block";
  if (verdictBadge) {
    verdictBadge.innerText = "EVALUATING...";
    verdictBadge.style.color = "var(--accent-cyan)";
  }

  const selectedDates = (typeof getSelectedDates === "function") ? getSelectedDates() : [];
  const dates = selectedDates.length > 0 ? selectedDates : ["2026_09_11"];
  const strategy = stratSel ? stratSel.value : "orb";
  const capital = parseFloat(capitalInput ? capitalInput.value : 100000) || 100000;
  const risk = parseFloat(riskInput ? riskInput.value : 1.0) || 1.0;
  const directory = dirInput ? dirInput.value.trim() : "";

  try {
    const resp = await fetch("/api/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        strategy: strategy,
        dates: dates,
        capital: capital,
        risk_pct: risk,
        directory: directory,
        symbols: ["auto"]
      })
    });

    const res = await resp.json();
    if (!resp.ok || res.status !== "success") {
      throw new Error(res.message || "Validation API returned an error");
    }

    const report = res.report || {};
    const hurdles = report.hurdles || {};
    const mc = report.monte_carlo || {};
    const dsr = report.deflated_sharpe || {};
    const score = report.overall_score !== undefined ? report.overall_score : (report.score_pct || 0);
    const verdict = report.verdict || "PASS";

    // Update Verdict Badge
    if (verdictBadge) {
      verdictBadge.innerText = `${verdict} (${score.toFixed(0)}%)`;
      if (verdict === "PASS") {
        verdictBadge.className = "badge badge-accent text-green";
      } else if (verdict === "MARGINAL") {
        verdictBadge.className = "badge badge-accent text-yellow";
      } else {
        verdictBadge.className = "badge badge-accent text-red";
      }
    }

    grid.innerHTML = `
      <!-- Card 1: Overfitting Hurdles -->
      <div class="validation-card">
        <h4><span>⚖️</span> Institutional Hurdles</h4>
        <div class="hurdle-list">
          <div class="hurdle-item">
            <span>Minimum Trade Count (≥30):</span>
            <span class="${hurdles.min_trades ? 'hurdle-pass' : 'hurdle-fail'} font-bold">${hurdles.min_trades ? '✓ PASS' : '✗ FAIL'}</span>
          </div>
          <div class="hurdle-item">
            <span>Positive Net Expectancy (P&L > ₹0):</span>
            <span class="${hurdles.positive_net_pnl ? 'hurdle-pass' : 'hurdle-fail'} font-bold">${hurdles.positive_net_pnl ? '✓ PASS' : '✗ FAIL'}</span>
          </div>
          <div class="hurdle-item">
            <span>Max Drawdown Tolerance (≤20%):</span>
            <span class="${hurdles.max_dd_acceptable ? 'hurdle-pass' : 'hurdle-fail'} font-bold">${hurdles.max_dd_acceptable ? '✓ PASS' : '✗ FAIL'}</span>
          </div>
          <div class="hurdle-item">
            <span>Profit Factor Floor (≥1.20):</span>
            <span class="${hurdles.profit_factor_ok ? 'hurdle-pass' : 'hurdle-fail'} font-bold">${hurdles.profit_factor_ok ? '✓ PASS' : '✗ FAIL'}</span>
          </div>
          <div class="hurdle-item">
            <span>Monte Carlo Win Probability (≥50%):</span>
            <span class="${hurdles.mc_win_probability ? 'hurdle-pass' : 'hurdle-fail'} font-bold">${hurdles.mc_win_probability ? '✓ PASS' : '✗ FAIL'}</span>
          </div>
          <div class="hurdle-item">
            <span>MC Resampled Max DD (≤25%):</span>
            <span class="${hurdles.mc_dd_acceptable ? 'hurdle-pass' : 'hurdle-fail'} font-bold">${hurdles.mc_dd_acceptable ? '✓ PASS' : '✗ FAIL'}</span>
          </div>
        </div>
      </div>

      <!-- Card 2: Monte Carlo Resampling Stress -->
      <div class="validation-card">
        <h4><span>🎲</span> Monte Carlo 1,000-Resample</h4>
        <div class="hurdle-list">
          <div class="hurdle-item">
            <span>Simulations Run:</span>
            <span class="font-mono text-cyan">${(mc.simulations_run || 1000).toLocaleString()} runs</span>
          </div>
          <div class="hurdle-item">
            <span>Probability of Profit:</span>
            <span class="font-bold ${(mc.prob_profitable || (mc.win_probability ? mc.win_probability * 100 : 0)) >= 50 ? 'text-green' : 'text-red'}">
              ${(mc.prob_profitable || (mc.win_probability ? (mc.win_probability * 100).toFixed(1) : 0))}%
            </span>
          </div>
          <div class="hurdle-item">
            <span>95% Worst Drawdown:</span>
            <span class="font-mono ${(mc.max_drawdown_95_pct || 0) <= 20 ? 'text-green' : 'text-red'}">
              ${(mc.max_drawdown_95_pct || 0).toFixed(2)}%
            </span>
          </div>
          <div class="hurdle-item">
            <span>Value-at-Risk (95% VaR):</span>
            <span class="font-mono text-muted">₹${(mc.var_95_inr || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</span>
          </div>
        </div>
      </div>

      <!-- Card 3: Deflated Sharpe & Statistical Tests -->
      <div class="validation-card">
        <h4><span>🔬</span> Deflated Sharpe & PBO</h4>
        <div class="hurdle-list">
          <div class="hurdle-item">
            <span>Deflated Sharpe Verdict:</span>
            <span class="font-bold ${dsr.verdict === 'SIGNIFICANT' ? 'text-green' : 'text-yellow'}">
              ${dsr.verdict || 'UNAUDITED'}
            </span>
          </div>
          <div class="hurdle-item">
            <span>DSR p-Value:</span>
            <span class="font-mono">${dsr.p_value !== undefined ? dsr.p_value.toFixed(4) : '—'}</span>
          </div>
          <div class="hurdle-item">
            <span>Overall Score:</span>
            <span class="font-bold text-cyan text-lg">${score.toFixed(1)}%</span>
          </div>
        </div>
      </div>
    `;

    showToast(`Validation Audit Complete: ${verdict} (${score.toFixed(0)}%)`, verdict === "PASS" ? "success" : "info");
  } catch (err) {
    if (verdictBadge) {
      verdictBadge.innerText = "AUDIT FAILED";
      verdictBadge.style.color = "var(--red)";
    }
    showToast("Validation failed: " + err.message, "error");
  }
}
window.runValidationAudit = runValidationAudit;

// 4. Trust & Risk Verdict Banner (TRUST-01)
function updateTrustBanner(m, trades) {
  const banner = document.getElementById("trustVerdictBanner");
  const icon = document.getElementById("trustBannerIcon");
  const title = document.getElementById("trustBannerTitle");
  const msg = document.getElementById("trustBannerMsg");

  if (!banner || !icon || !title || !msg) return;

  const tradeCount = trades ? trades.length : 0;
  const maxDD = m.max_drawdown_pct || 0;
  const netPnl = m.net_pnl || 0;

  banner.className = "trust-banner mb-14";

  if (tradeCount < 15) {
    banner.style.display = "flex";
    banner.classList.add("trust-banner-warn");
    icon.innerText = "⚠️";
    title.innerText = "Sample Size Warning (Underpowered Sample)";
    msg.innerText = `Only ${tradeCount} simulated trade(s) were executed. A sample size under 30 trades has low statistical confidence. Backtest over multiple historical sessions before production deployment.`;
  } else if (maxDD > 20) {
    banner.style.display = "flex";
    banner.classList.add("trust-banner-danger");
    icon.innerText = "🛑";
    title.innerText = "High Drawdown Regime Alert";
    msg.innerText = `Maximum peak-to-trough drawdown reached ${maxDD.toFixed(1)}%, breaching the standard 15% risk threshold. Adjust stop loss points or reduce position leverage.`;
  } else if (netPnl > 0 && tradeCount >= 30 && maxDD <= 15) {
    banner.style.display = "flex";
    banner.classList.add("trust-banner-success");
    icon.innerText = "🛡️";
    title.innerText = "Institutional Grade Candidate";
    msg.innerText = `Strategy demonstrated positive net expectancy across ${tradeCount} trades with controlled max drawdown (${maxDD.toFixed(1)}%). Candidate meets baseline robustness criteria.`;
  } else {
    banner.style.display = "none";
  }
}

// 5. Run History Persistence & Quick-Switch (HIST-01)
const RUN_HISTORY_KEY = "testing_engine_run_history";

function saveRunToHistory(runData) {
  try {
    let history = JSON.parse(localStorage.getItem(RUN_HISTORY_KEY) || "[]");
    const item = {
      id: "run_" + Date.now(),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      strategy: runData.strategy || "Strategy",
      pnl: runData.metrics ? (runData.metrics.net_pnl || 0) : 0,
      winRate: runData.metrics ? (runData.metrics.win_rate || 0) : 0,
      trades: runData.metrics ? (runData.metrics.total_trades || 0) : 0,
      raw: runData.raw
    };
    history.unshift(item);
    if (history.length > 10) history = history.slice(0, 10);
    localStorage.setItem(RUN_HISTORY_KEY, JSON.stringify(history));
    renderRunHistory();
  } catch (e) {
    console.warn("Could not save run to history:", e);
  }
}

function renderRunHistory() {
  const bar = document.getElementById("runHistoryBar");
  const list = document.getElementById("runHistoryList");
  if (!bar || !list) return;

  try {
    const history = JSON.parse(localStorage.getItem(RUN_HISTORY_KEY) || "[]");
    if (history.length === 0) {
      bar.style.display = "none";
      return;
    }

    bar.style.display = "flex";
    list.innerHTML = history.map((item, idx) => {
      const pnl = item.pnl || 0;
      const isProf = pnl >= 0;
      const pnlSign = isProf ? "+" : "";
      const pnlColor = isProf ? "var(--green)" : "var(--red)";
      return `
        <span class="history-chip" onclick="loadRunFromHistory('${item.id}')" title="${item.strategy} · ${item.trades} trades">
          <span>#${idx + 1}</span>
          <span style="color: ${pnlColor}; font-weight: 700;">${pnlSign}₹${Math.round(pnl).toLocaleString("en-IN")}</span>
          <span style="color: var(--text-muted); font-size: 0.68rem;">(${item.timestamp})</span>
        </span>
      `;
    }).join("");
  } catch (e) {}
}

function loadRunFromHistory(runId) {
  try {
    const history = JSON.parse(localStorage.getItem(RUN_HISTORY_KEY) || "[]");
    const found = history.find(h => h.id === runId);
    if (found && found.raw) {
      renderResults(found.raw);
      showToast(`Loaded Run ${found.timestamp}: ${found.strategy} (${found.pnl >= 0 ? '+' : ''}₹${found.pnl.toFixed(2)})`, "info");
    }
  } catch (e) {
    showToast("Failed to load historical run: " + e.message, "error");
  }
}
window.loadRunFromHistory = loadRunFromHistory;

// 6. Form State Persistence (STORE-01)
const FORM_STORAGE_KEY = "testing_engine_form_state";

function saveFormState() {
  const state = {
    strategy: document.getElementById("strategySelect")?.value,
    timeframe: document.getElementById("timeframeSelect")?.value,
    symbols: document.getElementById("symbolsInput")?.value,
    capital: document.getElementById("capitalInput")?.value,
    risk: document.getElementById("riskPctInput")?.value,
    dir: document.getElementById("dirInput")?.value
  };
  try {
    localStorage.setItem(FORM_STORAGE_KEY, JSON.stringify(state));
  } catch (e) {}
}

function restoreFormState() {
  try {
    const raw = localStorage.getItem(FORM_STORAGE_KEY);
    if (!raw) return;
    const s = JSON.parse(raw);
    if (s.strategy) {
      const sel = document.getElementById("strategySelect");
      if (sel) {
        sel.value = s.strategy;
        sel.dispatchEvent(new Event("change"));
      }
    }
    if (s.timeframe && document.getElementById("timeframeSelect")) {
      document.getElementById("timeframeSelect").value = s.timeframe;
    }
    if (s.symbols && document.getElementById("symbolsInput")) {
      document.getElementById("symbolsInput").value = s.symbols;
    }
    if (s.capital && document.getElementById("capitalInput")) {
      document.getElementById("capitalInput").value = s.capital;
    }
    if (s.risk && document.getElementById("riskPctInput")) {
      document.getElementById("riskPctInput").value = s.risk;
    }
    if (s.dir && document.getElementById("dirInput")) {
      document.getElementById("dirInput").value = s.dir;
    }
  } catch (e) {}
}

// 7. Workflow Load to Console (XFER-01)
function transferParamsToConsole(strategyName, params) {
  const mappedKey = Object.keys(STRATEGY_CATALOG_MAP).find(k => STRATEGY_CATALOG_MAP[k] === strategyName) || strategyName;
  applyParametersToConsole(mappedKey, params);
  switchTab("tabConsole");
  showToast(`Transferred ${strategyName} parameters to Backtest Console!`, "success");
}
window.transferParamsToConsole = transferParamsToConsole;

// 8. Strategy Presets (PRESET-01)
const PRESETS_STORAGE_KEY = "testing_engine_presets";

function initPresets() {
  const sel = document.getElementById("presetSelect");
  const btnSave = document.getElementById("btnSavePreset");
  if (!sel) return;

  const loadPresets = () => {
    try {
      const presets = JSON.parse(localStorage.getItem(PRESETS_STORAGE_KEY) || "[]");
      sel.innerHTML = '<option value="">⚙️ Presets (Default)</option>';
      presets.forEach((p, idx) => {
        const opt = document.createElement("option");
        opt.value = idx;
        opt.innerText = p.name;
        sel.appendChild(opt);
      });
    } catch (e) {}
  };

  sel.addEventListener("change", () => {
    const val = sel.value;
    if (val === "") return;
    try {
      const presets = JSON.parse(localStorage.getItem(PRESETS_STORAGE_KEY) || "[]");
      const p = presets[parseInt(val)];
      if (p) {
        if (p.strategy) {
          const stratSel = document.getElementById("strategySelect");
          if (stratSel) {
            stratSel.value = p.strategy;
            stratSel.dispatchEvent(new Event("change"));
          }
        }
        if (p.params) {
          applyParametersToConsole(p.strategy, p.params);
        }
        if (p.symbols && document.getElementById("symbolsInput")) {
          document.getElementById("symbolsInput").value = p.symbols;
        }
        showToast(`Loaded preset "${p.name}"!`, "success");
      }
    } catch (e) {
      showToast("Error loading preset: " + e.message, "error");
    }
  });

  if (btnSave) {
    btnSave.addEventListener("click", async () => {
      const strat = document.getElementById("strategySelect") ? document.getElementById("strategySelect").value : "orb";
      const defaultName = `${strat.toUpperCase()} Custom`;
      const name = await showPromptModal("Save Strategy Preset", "Enter a name for this preset configuration:", defaultName);
      if (!name) return;

      const currentParams = {};
      const fields = [
        "orbMinutesInput", "orbRrInput", "orbAtrMultInput",
        "stAtrPeriodInput", "stMultiplierInput", "stRrInput",
        "minScoreInput", "atrSlInput", "atrTgtInput",
        "camRrInput", "camBufferPtsInput",
        "ribbonFastInput", "ribbonMedInput", "ribbonSlowInput",
        "bbPeriodInput", "bbStdInput",
        "macdFastInput", "macdSlowInput", "macdSignalInput",
        "vwapBandMultInput", "vwapSlPtsInput", "vwapTgtPtsInput",
        "rsiPeriodInput", "rsiOverboughtInput", "rsiOversoldInput",
        "optionSlInput", "optionTgtInput"
      ];
      fields.forEach(f => {
        const el = document.getElementById(f);
        if (el && el.value !== undefined) {
          currentParams[f] = el.value;
        }
      });

      const preset = {
        name: name,
        strategy: strat,
        symbols: document.getElementById("symbolsInput") ? document.getElementById("symbolsInput").value : "auto",
        capital: document.getElementById("capitalInput") ? document.getElementById("capitalInput").value : "100000",
        risk: document.getElementById("riskPctInput") ? document.getElementById("riskPctInput").value : "1.0",
        params: currentParams,
        savedAt: new Date().toISOString()
      };

      try {
        const presets = JSON.parse(localStorage.getItem(PRESETS_STORAGE_KEY) || "[]");
        presets.push(preset);
        localStorage.setItem(PRESETS_STORAGE_KEY, JSON.stringify(presets));
        loadPresets();
        sel.value = presets.length - 1;
        showToast(`Saved preset "${name}"!`, "success");
      } catch (e) {
        showToast("Error saving preset: " + e.message, "error");
      }
    });
  }

  loadPresets();
}
window.initPresets = initPresets;

// 9. Export Center Dropdown & JSON Summary (EXP-01)
function initExportCenter() {
  const btnMenu = document.getElementById("btnExportMenu");
  const dropdown = document.getElementById("exportMenuDropdown");
  const btnJson = document.getElementById("btnExportJsonSummary");

  if (!btnMenu || !dropdown) return;

  btnMenu.addEventListener("click", (e) => {
    e.stopPropagation();
    const isShown = dropdown.style.display === "block";
    dropdown.style.display = isShown ? "none" : "block";
  });

  document.addEventListener("click", (e) => {
    if (!dropdown.contains(e.target) && e.target !== btnMenu) {
      dropdown.style.display = "none";
    }
  });

  if (btnJson) {
    btnJson.addEventListener("click", () => {
      dropdown.style.display = "none";
      if (!latest_run_cache) {
        showToast("No active backtest results available to export.", "warning");
        return;
      }
      const blob = new Blob([JSON.stringify(latest_run_cache, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `backtest_summary_${Date.now()}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast("Exported JSON Summary!", "success");
    });
  }
}
window.initExportCenter = initExportCenter;





// ── Calendar P&L Matrix & Weekday Performance Breakdown (VIZ-01) ─────────────
function renderCalendarHeatmap(dailyPnls, trades) {
  const container = document.getElementById("calendarHeatmapGrid");
  if (!container) return;

  const dayMap = {};
  if (Array.isArray(dailyPnls) && dailyPnls.length > 0) {
    dailyPnls.forEach(d => {
      const dateKey = (d.date || "").replace(/_/g, "-");
      if (dateKey) {
        dayMap[dateKey] = (dayMap[dateKey] || 0) + (d.net_pnl || 0);
      }
    });
  }

  if (Object.keys(dayMap).length <= 1 && Array.isArray(trades) && trades.length > 0) {
    trades.forEach(t => {
      if (t.exit_time) {
        const dateKey = t.exit_time.split(" ")[0].replace(/_/g, "-");
        dayMap[dateKey] = (dayMap[dateKey] || 0) + (t.net_pnl || 0);
      }
    });
  }

  const dateKeys = Object.keys(dayMap).sort();
  if (dateKeys.length === 0) {
    container.innerHTML = '<div class="empty-state text-xs">Execute backtest to view daily calendar heatmap.</div>';
    return;
  }

  let maxAbsPnl = 0;
  dateKeys.forEach(k => {
    const abs = Math.abs(dayMap[k]);
    if (abs > maxAbsPnl) maxAbsPnl = abs;
  });
  if (maxAbsPnl === 0) maxAbsPnl = 1;

  container.innerHTML = dateKeys.map(date => {
    const pnl = dayMap[date];
    const isProfit = pnl > 0;
    const isLoss = pnl < 0;
    const ratio = Math.abs(pnl) / maxAbsPnl;

    let heatClass = "heat-neutral";
    if (isProfit) {
      if (ratio > 0.6) heatClass = "heat-win-3";
      else if (ratio > 0.25) heatClass = "heat-win-2";
      else heatClass = "heat-win-1";
    } else if (isLoss) {
      if (ratio > 0.6) heatClass = "heat-loss-3";
      else if (ratio > 0.25) heatClass = "heat-loss-2";
      else heatClass = "heat-loss-1";
    }

    const sign = isProfit ? "+" : "";
    const pnlDisplay = Math.abs(pnl) >= 1000
      ? `${sign}₹${(pnl / 1000).toFixed(1)}k`
      : `${sign}₹${Math.round(pnl)}`;

    const parts = date.split("-");
    const label = parts.length === 3 ? `${parts[1]}/${parts[2]}` : date;

    return `
      <div class="calendar-day-cell ${heatClass}" title="Date: ${date} | Net P&L: ${sign}₹${pnl.toFixed(2)}">
        <span class="day-label">${label}</span>
        <span class="day-pnl">${pnlDisplay}</span>
      </div>
    `;
  }).join("");
}
window.renderCalendarHeatmap = renderCalendarHeatmap;

function renderWeekdayBreakdown(trades, dailyPnls) {
  const container = document.getElementById("weekdayBarsContainer");
  if (!container) return;

  const weekdayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  const displayDays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
  const stats = {
    Monday: { pnl: 0, trades: 0, wins: 0 },
    Tuesday: { pnl: 0, trades: 0, wins: 0 },
    Wednesday: { pnl: 0, trades: 0, wins: 0 },
    Thursday: { pnl: 0, trades: 0, wins: 0 },
    Friday: { pnl: 0, trades: 0, wins: 0 }
  };

  if (Array.isArray(trades) && trades.length > 0) {
    trades.forEach(t => {
      if (t.exit_time) {
        const dateStr = t.exit_time.split(" ")[0].replace(/_/g, "-");
        const dayIdx = new Date(dateStr).getDay();
        const dayName = weekdayNames[dayIdx];
        if (stats[dayName]) {
          stats[dayName].pnl += (t.net_pnl || 0);
          stats[dayName].trades += 1;
          if ((t.net_pnl || 0) > 0) stats[dayName].wins += 1;
        }
      }
    });
  } else if (Array.isArray(dailyPnls) && dailyPnls.length > 0) {
    dailyPnls.forEach(d => {
      const dateStr = (d.date || "").replace(/_/g, "-");
      const dayIdx = new Date(dateStr).getDay();
      const dayName = weekdayNames[dayIdx];
      if (stats[dayName]) {
        stats[dayName].pnl += (d.net_pnl || 0);
        stats[dayName].trades += 1;
        if ((d.net_pnl || 0) > 0) stats[dayName].wins += 1;
      }
    });
  }

  let maxAbsPnl = 0;
  displayDays.forEach(day => {
    const abs = Math.abs(stats[day].pnl);
    if (abs > maxAbsPnl) maxAbsPnl = abs;
  });
  if (maxAbsPnl === 0) maxAbsPnl = 1;

  container.innerHTML = displayDays.map(day => {
    const s = stats[day];
    const isProfit = s.pnl >= 0;
    const sign = isProfit ? "+" : "";
    const winRate = s.trades > 0 ? ((s.wins / s.trades) * 100).toFixed(0) : "0";
    const barWidth = Math.max(Math.round((Math.abs(s.pnl) / maxAbsPnl) * 100), 2);
    const barColorClass = isProfit ? "pos" : "neg";
    const shortDay = day.slice(0, 3);

    return `
      <div class="weekday-row">
        <span class="weekday-label">${shortDay}</span>
        <div class="weekday-bar-track">
          <div class="weekday-bar-fill ${barColorClass}" style="width: ${s.trades > 0 ? barWidth : 0}%;"></div>
        </div>
        <span class="weekday-stats ${isProfit ? 'text-green' : 'text-red'}">
          ${sign}₹${Math.round(s.pnl).toLocaleString("en-IN")} (${s.trades}T · ${winRate}%W)
        </span>
      </div>
    `;
  }).join("");
}
window.renderWeekdayBreakdown = renderWeekdayBreakdown;

// ── Walk-Forward Robustness Traffic Light Gauge (VIZ-03) ───────────────────────
function updateWfoTrafficLight(wfe) {
  const lightRobust = document.getElementById("wfoLightRobust");
  const lightModerate = document.getElementById("wfoLightModerate");
  const lightDegraded = document.getElementById("wfoLightDegraded");

  if (!lightRobust || !lightModerate || !lightDegraded) return;

  lightRobust.classList.remove("active");
  lightModerate.classList.remove("active");
  lightDegraded.classList.remove("active");

  if (wfe >= 0.70) {
    lightRobust.classList.add("active");
  } else if (wfe >= 0.50) {
    lightModerate.classList.add("active");
  } else {
    lightDegraded.classList.add("active");
  }
}
window.updateWfoTrafficLight = updateWfoTrafficLight;

// ── 2D Parameter Stability Landscape Matrix (VIZ-04) ──────────────────────────
function renderMassStabilityMatrix(results) {
  const matrixCard = document.getElementById("massStabilityMatrixCard");
  const container = document.getElementById("stabilityMatrixContainer");
  const selX = document.getElementById("matrixParamX");
  const selY = document.getElementById("matrixParamY");

  if (!matrixCard || !container || !results) return;

  const runs = results.runs || results.ranked || [];
  if (runs.length === 0) {
    container.innerHTML = '<div class="empty-state text-xs">No simulation runs available to construct stability matrix.</div>';
    matrixCard.style.display = "block";
    return;
  }

  const paramKeysSet = new Set();
  runs.forEach(r => {
    if (r.params) {
      Object.keys(r.params).forEach(k => paramKeysSet.add(k));
    }
  });
  const paramKeys = Array.from(paramKeysSet);

  if (paramKeys.length === 0) {
    container.innerHTML = '<div class="empty-state text-xs">Simulation runs did not include multi-parameter dimensions.</div>';
    matrixCard.style.display = "block";
    return;
  }

  if (selX && selY && (selX.options.length === 0 || selX.dataset.loadedKeys !== paramKeys.join(","))) {
    selX.innerHTML = "";
    selY.innerHTML = "";
    paramKeys.forEach((k) => {
      const optX = document.createElement("option");
      optX.value = k;
      optX.innerText = k;
      selX.appendChild(optX);

      const optY = document.createElement("option");
      optY.value = k;
      optY.innerText = k;
      selY.appendChild(optY);
    });
    selX.dataset.loadedKeys = paramKeys.join(",");
    selX.selectedIndex = 0;
    selY.selectedIndex = Math.min(1, paramKeys.length - 1);
  }

  const pX = selX ? selX.value : paramKeys[0];
  const pY = selY ? selY.value : (paramKeys[1] || paramKeys[0]);

  const xValues = Array.from(new Set(runs.map(r => r.params ? r.params[pX] : null).filter(v => v !== null && v !== undefined))).sort((a, b) => a - b);
  const yValues = Array.from(new Set(runs.map(r => r.params ? r.params[pY] : null).filter(v => v !== null && v !== undefined))).sort((a, b) => a - b);

  const gridMap = {};
  let minSharpe = Infinity;
  let maxSharpe = -Infinity;

  runs.forEach(r => {
    if (!r.params) return;
    const x = r.params[pX];
    const y = r.params[pY];
    const sharpe = (r.metrics ? r.metrics.sharpe_ratio : r.sharpe) || 0;
    const pnl = (r.metrics ? r.metrics.net_pnl : r.net_pnl) || 0;
    const cellKey = `${x}|${y}`;

    if (!gridMap[cellKey] || sharpe > gridMap[cellKey].sharpe) {
      gridMap[cellKey] = { sharpe, pnl, run: r };
    }
    if (sharpe < minSharpe) minSharpe = sharpe;
    if (sharpe > maxSharpe) maxSharpe = sharpe;
  });

  if (minSharpe === Infinity) { minSharpe = 0; maxSharpe = 1; }
  const range = maxSharpe - minSharpe || 1;

  let html = `<table class="stability-grid-table"><thead><tr><th style="color: var(--accent-cyan); font-weight: 700;">${pY} \\ ${pX}</th>`;
  xValues.forEach(x => {
    html += `<th>${x}</th>`;
  });
  html += '</tr></thead><tbody>';

  yValues.forEach(y => {
    html += `<tr><th style="color: var(--accent-cyan); text-align: right; padding-right: 10px;">${y}</th>`;
    xValues.forEach(x => {
      const item = gridMap[`${x}|${y}`];
      if (item) {
        const norm = (item.sharpe - minSharpe) / range;
        let bgStyle = norm >= 0.6
          ? `background: rgba(16, 185, 129, ${0.15 + norm * 0.45}); color: #10b981;`
          : norm >= 0.3
            ? `background: rgba(0, 242, 254, ${0.1 + norm * 0.35}); color: var(--accent-cyan);`
            : `background: rgba(239, 68, 68, ${0.1 + (1 - norm) * 0.2}); color: #ef4444;`;

        html += `
          <td class="stability-cell" style="${bgStyle}" title="${pX}=${x}, ${pY}=${y} | Sharpe: ${item.sharpe.toFixed(2)} | Net P&L: ₹${item.pnl.toFixed(2)}">
            <span class="stability-val">${item.sharpe.toFixed(2)}</span>
          </td>
        `;
      } else {
        html += '<td class="stability-cell empty" style="color: var(--text-muted); opacity: 0.3;">—</td>';
      }
    });
    html += '</tr>';
  });
  html += '</tbody></table>';

  container.innerHTML = html;
  matrixCard.style.display = "block";
}
window.renderMassStabilityMatrix = renderMassStabilityMatrix;

// ── Dynamic Strategy Parameter Forms (DYN-01) ─────────────────────────────────
async function renderDynamicParams(strategyKey) {
  const container = document.getElementById("dynamicParamsGrid");
  const block = document.getElementById("dynamicParamsBlock");
  if (!container || !block) return;

  container.innerHTML = `<div class="empty-state text-xs">Loading parameter metadata for ${strategyKey}...</div>`;
  block.style.display = "block";

  try {
    let params = null;
    if (window.strategyCatalog) {
      const found = window.strategyCatalog.find(s => s.key === strategyKey);
      if (found && Array.isArray(found.parameters) && found.parameters.length > 0) {
        params = found.parameters;
      }
    }

    if (!params) {
      const resp = await fetch(`/api/strategy_params?strategy=${encodeURIComponent(strategyKey)}`);
      if (resp.ok) {
        const data = await resp.json();
        if (Array.isArray(data.parameters)) {
          params = data.parameters;
        } else if (data.default_grid) {
          params = Object.keys(data.default_grid).map(k => ({
            name: k,
            label: k.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase()),
            default: Array.isArray(data.default_grid[k]) ? data.default_grid[k][0] : data.default_grid[k],
            type: typeof (Array.isArray(data.default_grid[k]) ? data.default_grid[k][0] : data.default_grid[k]) === "number" ? "number" : "text"
          }));
        }
      }
    }

    if (!params || params.length === 0) {
      container.innerHTML = '<div class="text-xs text-muted" style="padding: 6px;">Strategy utilizes default institutional execution parameters.</div>';
      return;
    }

    container.innerHTML = params.map(p => {
      const key = p.name || p.key || p.id;
      const label = p.label || key.replace(/_/g, " ").toUpperCase();
      const val = p.default !== undefined ? p.default : (p.value !== undefined ? p.value : "");
      const isBool = p.type === "bool" || typeof val === "boolean";
      const hasChoices = (p.choices && Array.isArray(p.choices) && p.choices.length > 0) || p.type === "choice";
      const isNum = !isBool && !hasChoices && (typeof val === "number" || p.type === "number" || p.type === "int" || p.type === "float");
      const step = (p.step || (isNum ? (String(val).includes(".") ? "0.1" : "1") : undefined));
      const descHint = p.description ? `<small class="text-muted block text-xs" style="margin-top: 2px;">${p.description}</small>` : '';

      if (isBool) {
        return `
          <div class="dynamic-param-field form-group" style="padding-top: 18px;">
            <div class="flex-align flex-gap-8">
              <input type="checkbox"
                     id="dynParam_${key}"
                     data-param-key="${key}"
                     ${Boolean(val) ? 'checked' : ''}
                     style="width: 16px; height: 16px; cursor: pointer;">
              <label for="dynParam_${key}" style="margin-bottom: 0; cursor: pointer; font-weight: 500;">${label}</label>
            </div>
            ${descHint}
          </div>
        `;
      }

      if (hasChoices) {
        const opts = (p.choices || []).map(c => `<option value="${c}" ${String(c) === String(val) ? 'selected' : ''}>${c}</option>`).join("");
        return `
          <div class="dynamic-param-field form-group">
            <label for="dynParam_${key}">${label}:</label>
            <select id="dynParam_${key}" data-param-key="${key}" class="form-control">
              ${opts}
            </select>
            ${descHint}
          </div>
        `;
      }

      if (isNum) {
        const minAttr = (p.min !== undefined && p.min !== null) ? `min="${p.min}"` : '';
        const maxAttr = (p.max !== undefined && p.max !== null) ? `max="${p.max}"` : '';
        return `
          <div class="dynamic-param-field form-group">
            <label for="dynParam_${key}">${label}:</label>
            <input type="number"
                   id="dynParam_${key}"
                   data-param-key="${key}"
                   value="${val}"
                   ${minAttr}
                   ${maxAttr}
                   ${step ? `step="${step}"` : ''}
                   class="form-control">
            ${descHint}
          </div>
        `;
      }

      return `
        <div class="dynamic-param-field form-group">
          <label for="dynParam_${key}">${label}:</label>
          <input type="text"
                 id="dynParam_${key}"
                 data-param-key="${key}"
                 value="${val}"
                 class="form-control">
          ${descHint}
        </div>
      `;
    }).join("");
  } catch (err) {
    container.innerHTML = '<div class="text-xs text-muted">Parameters loaded using standard baseline.</div>';
  }
}
window.renderDynamicParams = renderDynamicParams;

// ── Command Palette (Ctrl+K / Cmd+K) (CMD-01) ─────────────────────────────────
function initCommandPalette() {
  const backdrop = document.getElementById("commandPaletteBackdrop");
  const input = document.getElementById("commandPaletteInput");
  const resultsContainer = document.getElementById("commandPaletteResults");
  const btnTrigger = document.getElementById("btnCommandPalette");

  if (!backdrop || !input || !resultsContainer) return;

  let activeIndex = 0;
  let filteredCommands = [];

  const commands = [
    // Workflow Navigation
    { id: "nav-console", title: "Go to Backtest Console", category: "Navigation", icon: "⚙️", action: () => switchTab("tabConsole") },
    { id: "nav-analytics", title: "Go to Results & Analytics", category: "Navigation", icon: "📊", action: () => switchTab("tabAnalytics") },
    { id: "nav-inspector", title: "Go to Trade Inspector & Log", category: "Navigation", icon: "🔍", action: () => switchTab("tabInspector") },
    { id: "nav-explorer", title: "Go to Market Data Explorer", category: "Navigation", icon: "🗄️", action: () => switchTab("tabExplorer") },
    { id: "nav-wfo", title: "Go to Walk-Forward Lab", category: "Navigation", icon: "🧪", action: () => switchTab("tabWalkForward") },
    { id: "nav-optimizer", title: "Go to Parameter Optimizer", category: "Navigation", icon: "🎛️", action: () => switchTab("tabOptimizer") },
    { id: "nav-mass", title: "Go to Mass Iteration Lab", category: "Navigation", icon: "🚀", action: () => switchTab("tabMassIteration") },

    // Core Backtest Execution
    { id: "act-run", title: "⚡ Run Backtest Simulation", category: "Execution", icon: "⚡", shortcut: "Ctrl+Enter", action: () => runBacktest() },
    { id: "act-tearsheet", title: "📄 Open Institutional HTML Tearsheet", category: "Reporting", icon: "📄", action: () => openTearsheet() },
    { id: "act-export-csv", title: "📊 Export Trade Log to CSV", category: "Reporting", icon: "📥", action: () => { window.location.href = "/api/export_csv"; } },
    { id: "act-validation", title: "🛡️ Run Institutional Robustness Audit", category: "Validation", icon: "🛡️", action: () => runValidationAudit() },
    { id: "act-browse", title: "📁 Browse Market Data Files", category: "Data Layer", icon: "📁", action: () => openFileBrowser() },
    { id: "act-save-preset", title: "💾 Save Current Configuration as Preset", category: "Preset", icon: "💾", action: () => {
      const btn = document.getElementById("btnSavePreset");
      if (btn) btn.click();
    }},

    // Quick Strategy Switching
    { id: "strat-equity", title: "Switch Strategy: Equity Momentum (v4/v5)", category: "Strategies", icon: "📈", action: () => setStrategy("equity") },
    { id: "strat-supertrend", title: "Switch Strategy: Supertrend Follower", category: "Strategies", icon: "📈", action: () => setStrategy("supertrend") },
    { id: "strat-orb", title: "Switch Strategy: Opening Range Breakout (ORB)", category: "Strategies", icon: "⚡", action: () => setStrategy("orb") },
    { id: "strat-options", title: "Switch Strategy: NIFTY Options Breakout", category: "Strategies", icon: "🎯", action: () => setStrategy("options") },
    { id: "strat-straddle", title: "Switch Strategy: 09:20 Short Straddle", category: "Strategies", icon: "⏳", action: () => setStrategy("short-straddle") },
    { id: "strat-camarilla", title: "Switch Strategy: Camarilla Floor Pivot Breakout", category: "Strategies", icon: "📐", action: () => setStrategy("camarilla") },
    { id: "strat-ribbon", title: "Switch Strategy: EMA Ribbon Alignment", category: "Strategies", icon: "🌊", action: () => setStrategy("ema-ribbon") },
    { id: "strat-ai", title: "Switch Strategy: AI Decision Replay", category: "Strategies", icon: "🧠", action: () => setStrategy("ai-replay") }
  ];

  function setStrategy(stratKey) {
    const sel = document.getElementById("strategySelect");
    if (sel) {
      sel.value = stratKey;
      sel.dispatchEvent(new Event("change"));
      switchTab("tabConsole");
      showToast(`Switched strategy to ${stratKey.toUpperCase()}`, "info");
    }
  }

  function openPalette() {
    backdrop.style.display = "flex";
    backdrop.setAttribute("aria-hidden", "false");
    input.value = "";
    activeIndex = 0;
    renderPaletteItems(commands);
    setTimeout(() => input.focus(), 30);
  }

  function closePalette() {
    backdrop.style.display = "none";
    backdrop.setAttribute("aria-hidden", "true");
  }

  function renderPaletteItems(list) {
    filteredCommands = list;
    if (list.length === 0) {
      resultsContainer.innerHTML = '<div class="empty-state text-xs">No matching commands or actions found.</div>';
      return;
    }

    resultsContainer.innerHTML = list.map((item, idx) => `
      <div class="command-palette-item ${idx === activeIndex ? 'active' : ''}" data-index="${idx}">
        <span class="cmd-item-icon">${item.icon}</span>
        <div class="cmd-item-info">
          <span class="cmd-item-title">${item.title}</span>
          <span class="cmd-item-category">${item.category}</span>
        </div>
        ${item.shortcut ? `<span class="cmd-item-shortcut">${item.shortcut}</span>` : ''}
      </div>
    `).join("");

    resultsContainer.querySelectorAll(".command-palette-item").forEach(el => {
      el.addEventListener("click", () => {
        const idx = parseInt(el.getAttribute("data-index"));
        executeCommand(idx);
      });
      el.addEventListener("mouseenter", () => {
        const idx = parseInt(el.getAttribute("data-index"));
        setActiveItem(idx);
      });
    });
  }

  function setActiveItem(idx) {
    activeIndex = Math.max(0, Math.min(idx, filteredCommands.length - 1));
    const items = resultsContainer.querySelectorAll(".command-palette-item");
    items.forEach((it, i) => {
      if (i === activeIndex) {
        it.classList.add("active");
        it.scrollIntoView({ block: "nearest" });
      } else {
        it.classList.remove("active");
      }
    });
  }

  function executeCommand(idx) {
    if (filteredCommands[idx] && typeof filteredCommands[idx].action === "function") {
      closePalette();
      filteredCommands[idx].action();
    }
  }

  input.addEventListener("input", () => {
    const q = input.value.trim().toLowerCase();
    activeIndex = 0;
    if (!q) {
      renderPaletteItems(commands);
      return;
    }
    const matched = commands.filter(c =>
      c.title.toLowerCase().includes(q) ||
      c.category.toLowerCase().includes(q) ||
      c.id.toLowerCase().includes(q)
    );
    renderPaletteItems(matched);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveItem(activeIndex + 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveItem(activeIndex - 1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      executeCommand(activeIndex);
    } else if (e.key === "Escape") {
      e.preventDefault();
      closePalette();
    }
  });

  window.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
      e.preventDefault();
      if (backdrop.style.display === "flex") {
        closePalette();
      } else {
        openPalette();
      }
    }
  });

  if (btnTrigger) {
    btnTrigger.addEventListener("click", openPalette);
  }

  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) {
      closePalette();
    }
  });
}
window.initCommandPalette = initCommandPalette;

// ── Master Clean Namespacing & Modular Architecture (MOD-01) ──────────────────
window.Dashboard = {
  ChartRegistry: window.ChartRegistry,
  switchTab: window.switchTab,
  runBacktest: window.runBacktest,
  openTearsheet: window.openTearsheet,
  showToast: window.showToast,
  showPromptModal: window.showPromptModal,
  renderCalendarHeatmap: window.renderCalendarHeatmap,
  renderWeekdayBreakdown: window.renderWeekdayBreakdown,
  updateWfoTrafficLight: window.updateWfoTrafficLight,
  renderMassStabilityMatrix: window.renderMassStabilityMatrix,
  renderDynamicParams: window.renderDynamicParams,
  initCommandPalette: window.initCommandPalette
};
