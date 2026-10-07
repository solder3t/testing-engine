// trading_engine.js — Trading Engine Deep Integration & Insights Cockpit
// Provides Live vs Sim Reconciliation, Gemini AI Calibration, Factor Alpha Attribution,
// Monte Carlo Stress Testing, Multi-Leg Greeks Simulation, Option Chain & OI,
// Forensic Tape Replay, Overfitting Defense, Portfolio Allocation, and Auto-Tuning.

let teDriftChartInstance = null;
let teCalibrationChartInstance = null;
let teMonteCarloChartInstance = null;
let teGreeksChartInstance = null;
let teOptionChainChartInstance = null;
let tePcrChartInstance = null;
let teReplayChartInstance = null;
let tePortfolioChartInstance = null;
let currentReplaySession = null;
let currentReplayFrameIndex = 0;
let replayIntervalTimer = null;
let replayIsPlaying = false;

function roundTo(num, decimals = 2) {
  if (num === null || num === undefined || isNaN(num)) return 0;
  const factor = Math.pow(10, decimals);
  return Math.round((Number(num) + Number.EPSILON) * factor) / factor;
}

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

      if (subId === "subReconciliation") {
        setTimeout(() => { if (teDriftChartInstance) teDriftChartInstance.resize(); }, 50);
      } else if (subId === "subFactorAlpha" && !window._teFactorsLoaded) {
        window._teFactorsLoaded = true;
        fetchFactorAblation();
      } else if (subId === "subConfigExport" && !window._teConfigLoaded) {
        window._teConfigLoaded = true;
        fetchConfigExport();
      } else if (subId === "subAiAnalytics") {
        setTimeout(() => { if (teCalibrationChartInstance) teCalibrationChartInstance.resize(); }, 50);
        if (!window._latestAiAnalyticsData) fetchAiAnalytics();
      } else if (subId === "subMonteCarlo") {
        setTimeout(() => { if (teMonteCarloChartInstance) teMonteCarloChartInstance.resize(); }, 50);
        if (!window._teMonteCarloLoaded) {
          window._teMonteCarloLoaded = true;
          fetchMonteCarlo();
        }
      } else if (subId === "subMultiLeg") {
        setTimeout(() => { if (teGreeksChartInstance) teGreeksChartInstance.resize(); }, 50);
        if (!window._teMultiLegLoaded) {
          window._teMultiLegLoaded = true;
          fetchMultiLegSimulation();
        }
      } else if (subId === "subOptionChain") {
        setTimeout(() => {
          if (teOptionChainChartInstance) teOptionChainChartInstance.resize();
          if (tePcrChartInstance) tePcrChartInstance.resize();
        }, 50);
        if (!window._teOptionChainLoaded) {
          window._teOptionChainLoaded = true;
          fetchOptionChain();
        }
      } else if (subId === "subForensicReplay") {
        setTimeout(() => { if (teReplayChartInstance) teReplayChartInstance.resize(); }, 50);
        if (!window._teReplayLoaded) {
          window._teReplayLoaded = true;
          loadReplaySession();
        }
      } else if (subId === "subRobustness") {
        if (!window._teRobustnessLoaded) {
          window._teRobustnessLoaded = true;
          fetchRobustnessAudit();
        }
      } else if (subId === "subPortfolioAllocation") {
        setTimeout(() => { if (tePortfolioChartInstance) tePortfolioChartInstance.resize(); }, 50);
        if (!window._tePortfolioLoaded) {
          window._tePortfolioLoaded = true;
          fetchPortfolioOptimization();
        }
      } else if (subId === "subAutoTune") {
        if (!window._teAutoTuneLoaded) {
          window._teAutoTuneLoaded = true;
          fetchAutoTune();
        }
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

  // Option Chain Handlers
  const btnRefreshOptionChain = document.getElementById("btnRefreshOptionChain");
  if (btnRefreshOptionChain) btnRefreshOptionChain.addEventListener("click", fetchOptionChain);
  const ocTableSelect = document.getElementById("ocTableSelect");
  if (ocTableSelect) ocTableSelect.addEventListener("change", fetchOptionChain);
  const ocTimeSlider = document.getElementById("ocTimeSlider");
  if (ocTimeSlider) {
    ocTimeSlider.addEventListener("input", (e) => {
      const label = document.getElementById("ocTimeLabel");
      const val = parseInt(e.target.value);
      if (label) {
        if (val >= 75) label.innerText = "EOD";
        else {
          const totalMin = val * 5;
          const h = 9 + Math.floor((15 + totalMin) / 60);
          const m = (15 + totalMin) % 60;
          label.innerText = `${h}:${String(m).padStart(2, '0')}`;
        }
      }
    });
    ocTimeSlider.addEventListener("change", fetchOptionChain);
  }

  // Forensic Replay Handlers
  const btnLoadReplay = document.getElementById("btnLoadReplay");
  if (btnLoadReplay) btnLoadReplay.addEventListener("click", loadReplaySession);
  const btnReplayPlay = document.getElementById("btnReplayPlay");
  if (btnReplayPlay) btnReplayPlay.addEventListener("click", toggleReplayPlay);
  const btnReplayStepBack = document.getElementById("btnReplayStepBack");
  if (btnReplayStepBack) btnReplayStepBack.addEventListener("click", () => stepReplay(-1));
  const btnReplayStepForward = document.getElementById("btnReplayStepForward");
  if (btnReplayStepForward) btnReplayStepForward.addEventListener("click", () => stepReplay(1));
  const btnReplayReset = document.getElementById("btnReplayReset");
  if (btnReplayReset) btnReplayReset.addEventListener("click", resetReplay);
  const replayScrubber = document.getElementById("replayScrubber");
  if (replayScrubber) {
    replayScrubber.addEventListener("input", (e) => {
      seekReplay(parseInt(e.target.value));
    });
  }
  const chkReplaySt = document.getElementById("chkReplaySt");
  const chkReplayVwap = document.getElementById("chkReplayVwap");
  const chkReplayCpr = document.getElementById("chkReplayCpr");
  [chkReplaySt, chkReplayVwap, chkReplayCpr].forEach(chk => {
    if (chk) chk.addEventListener("change", () => renderReplayFrame(currentReplayFrameIndex));
  });

  // Robustness Handlers
  const btnRunRobustness = document.getElementById("btnRunRobustness");
  if (btnRunRobustness) btnRunRobustness.addEventListener("click", fetchRobustnessAudit);

  // Portfolio Handlers
  const btnRunPortfolio = document.getElementById("btnRunPortfolio");
  if (btnRunPortfolio) btnRunPortfolio.addEventListener("click", () => {
    const activePreset = document.querySelector(".port-preset-btn.active");
    fetchPortfolioOptimization(activePreset ? activePreset.getAttribute("data-method") : "risk_parity");
  });
  document.querySelectorAll(".port-preset-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".port-preset-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      fetchPortfolioOptimization(btn.getAttribute("data-method"));
    });
  });

  // Auto-Tune Handlers
  const btnRunAutoTune = document.getElementById("btnRunAutoTune");
  if (btnRunAutoTune) btnRunAutoTune.addEventListener("click", fetchAutoTune);
  const btnApplyAutoTune = document.getElementById("btnApplyAutoTune");
  if (btnApplyAutoTune) btnApplyAutoTune.addEventListener("click", applyAutoTune);


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
    const dirInput = document.getElementById("dirInput");
    const dirParam = dirInput && dirInput.value ? `?dir=${encodeURIComponent(dirInput.value.trim())}` : "";
    const res = await fetch(`/api/archives${dirParam}`);
    const json = await res.json();
    if ((json.status === "ok" || json.status === "success") && Array.isArray(json.archives)) {
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

  const pairs = Array.isArray(data) ? data : (data?.matched_pairs || []);
  const unprompted = Array.isArray(data?.unprompted_live) ? data.unprompted_live : [];
  const missed = Array.isArray(data?.missed_signals) ? data.missed_signals : [];

  const getTimeStr = (timeStr) => {
    if (!timeStr || typeof timeStr !== "string") return "";
    if (timeStr.includes(" ")) {
      const parts = timeStr.split(" ");
      return parts[1].substring(0, 5);
    }
    return timeStr.substring(0, 5);
  };

  const events = [];

  // 1. Matched pairs
  pairs.forEach(p => {
    const liveTime = getTimeStr(p.live_trade?.exit_time || p.live_trade?.entry_time);
    const simTime = getTimeStr((p.sim_trade || p.simulated_trade)?.exit_time || (p.sim_trade || p.simulated_trade)?.entry_time);
    const t = liveTime || simTime || "10:15";
    events.push({
      time: t,
      livePnl: Number(p.live_trade?.net_pnl || 0),
      simPnl: Number((p.sim_trade || p.simulated_trade)?.net_pnl || 0)
    });
  });

  // 2. Unprompted live trades
  unprompted.forEach(t => {
    const timeStr = getTimeStr(t.exit_time || t.entry_time) || "11:30";
    events.push({
      time: timeStr,
      livePnl: Number(t.net_pnl || 0),
      simPnl: 0
    });
  });

  // 3. Missed simulated trades
  missed.forEach(t => {
    const timeStr = getTimeStr(t.exit_time || t.entry_time) || "12:00";
    events.push({
      time: timeStr,
      livePnl: 0,
      simPnl: Number(t.net_pnl || 0)
    });
  });

  // If no trades found, show baseline flat curve
  if (events.length === 0) {
    events.push({ time: "09:30", livePnl: 0, simPnl: 0 });
    events.push({ time: "12:00", livePnl: 0, simPnl: 0 });
    events.push({ time: "15:15", livePnl: 0, simPnl: 0 });
  }

  events.sort((a, b) => a.time.localeCompare(b.time));

  let cumLive = 0;
  let cumSim = 0;
  const labels = ["09:15"];
  const liveSeries = [0];
  const simSeries = [0];

  events.forEach(pt => {
    cumLive += pt.livePnl;
    cumSim += pt.simPnl;
    labels.push(pt.time);
    liveSeries.push(roundTo(cumLive, 2));
    simSeries.push(roundTo(cumSim, 2));
  });

  if (labels[labels.length - 1] < "15:15") {
    labels.push("15:30");
    liveSeries.push(roundTo(cumLive, 2));
    simSeries.push(roundTo(cumSim, 2));
  }

  const badge = document.getElementById("teDriftBadge");
  if (badge) {
    const totalTrades = pairs.length + unprompted.length + missed.length;
    badge.innerText = totalTrades > 0 ? `${totalTrades} Trades Tracked` : "Session Baseline";
  }

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
          pointRadius: 4,
          pointHoverRadius: 6
        },
        {
          label: "Realized Live Paper P&L (₹)",
          data: liveSeries,
          borderColor: cumLive >= 0 ? "#00f5a0" : "#ff4d4f",
          backgroundColor: cumLive >= 0 ? "rgba(0, 245, 160, 0.08)" : "rgba(255, 77, 79, 0.08)",
          fill: true,
          tension: 0.2,
          borderWidth: 2,
          pointRadius: 4,
          pointHoverRadius: 6
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
          borderWidth: 1,
          callbacks: {
            label: (c) => `${c.dataset.label}: ₹${Number(c.parsed.y).toLocaleString()}`
          }
        }
      },
      scales: {
        x: {
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "#8b949e", font: { size: 10 } }
        },
        y: {
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: {
            color: "#8b949e",
            font: { size: 10 },
            callback: (v) => `₹${Number(v).toLocaleString()}`
          }
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

// ── 7. Option Chain & OI Profile ─────────────────────────────────────────────
async function fetchOptionChain() {
  const select = document.getElementById("teDateSelect");
  const dateStr = select ? select.value : "2026_09_11";
  const tblSelect = document.getElementById("ocTableSelect");
  const table = tblSelect && tblSelect.value ? tblSelect.value : "";
  const slider = document.getElementById("ocTimeSlider");
  const sliderVal = slider ? parseInt(slider.value) : 75;

  let timeParam = "";
  if (sliderVal < 75) {
    const totalMin = sliderVal * 5;
    const h = 9 + Math.floor((15 + totalMin) / 60);
    const m = (15 + totalMin) % 60;
    timeParam = `${h}:${String(m).padStart(2, '0')}`;
  }

  try {
    const url = `/api/trading_engine/option_chain?date=${encodeURIComponent(dateStr)}&table=${encodeURIComponent(table)}&time=${encodeURIComponent(timeParam)}`;
    const res = await fetch(url);
    const json = await res.json();
    if (json.status !== "ok") return;

    const d = json.data;

    // Populate tables dropdown if needed
    if (tblSelect && d.available_tables && d.available_tables.length > 0) {
      if (tblSelect.options.length <= 1 || !tblSelect.querySelector(`option[value="${d.table}"]`)) {
        tblSelect.innerHTML = d.available_tables.map(t => `<option value="${t}" ${t === d.table ? 'selected' : ''}>${t}</option>`).join("");
      }
    }

    // Update KPI Cards
    const kpiSpot = document.getElementById("ocKpiSpot");
    if (kpiSpot) kpiSpot.innerText = d.underlying_ltp ? `₹${d.underlying_ltp.toLocaleString()}` : "--";
    const kpiAtm = document.getElementById("ocKpiAtm");
    if (kpiAtm) kpiAtm.innerText = `ATM Strike: ${d.atm_strike || '--'}`;
    const kpiMaxPain = document.getElementById("ocKpiMaxPain");
    if (kpiMaxPain) kpiMaxPain.innerText = d.max_pain_strike ? `${d.max_pain_strike}` : "--";
    const kpiGammaFlip = document.getElementById("ocKpiGammaFlip");
    if (kpiGammaFlip) kpiGammaFlip.innerText = d.gamma_flip_strike ? `${d.gamma_flip_strike}` : "--";
    const kpiPcr = document.getElementById("ocKpiPcr");
    if (kpiPcr) {
      kpiPcr.innerText = d.pcr !== undefined ? d.pcr.toFixed(2) : "--";
      kpiPcr.style.color = d.pcr >= 1.0 ? 'var(--accent-green)' : 'var(--accent-red)';
    }
    const kpiOiTotal = document.getElementById("ocKpiOiTotal");
    if (kpiOiTotal) kpiOiTotal.innerText = `CE: ${(d.total_ce_oi || 0).toLocaleString()} | PE: ${(d.total_pe_oi || 0).toLocaleString()}`;

    // Render Charts
    renderOptionChainCharts(d);

    // Populate Table
    const tbody = document.getElementById("ocStrikesBody");
    if (tbody && d.strikes) {
      tbody.innerHTML = d.strikes.map(s => {
        const isAtm = Math.abs(s.strike_price - (d.atm_strike || 0)) < 25;
        const bg = isAtm ? 'rgba(0, 242, 254, 0.08)' : '';
        return `
          <tr style="background: ${bg};">
            <td style="color: var(--accent-cyan); font-size: 0.8rem;">${s.ce_iv || '--'}%</td>
            <td style="color: #fff; font-weight: 600;">₹${s.ce_ltp}</td>
            <td style="color: var(--text-muted); font-size: 0.8rem;">${s.ce_delta}</td>
            <td style="color: var(--accent-cyan); font-weight: 700;">${(s.ce_oi || 0).toLocaleString()}</td>
            <td style="font-weight: 800; color: #fff; background: rgba(255,255,255,0.04); text-align: center;">${s.strike_price}</td>
            <td style="color: var(--accent-red); font-weight: 700;">${(s.pe_oi || 0).toLocaleString()}</td>
            <td style="color: var(--text-muted); font-size: 0.8rem;">${s.pe_delta}</td>
            <td style="color: #fff; font-weight: 600;">₹${s.pe_ltp}</td>
            <td style="color: var(--accent-red); font-size: 0.8rem;">${s.pe_iv || '--'}%</td>
          </tr>
        `;
      }).join("");
    }
  } catch (err) {
    console.error("Error fetching option chain:", err);
  }
}

function renderOptionChainCharts(data) {
  // 1. Strike OI Distribution Chart
  const ctxOi = document.getElementById("teOptionChainChart");
  if (ctxOi && data.strikes) {
    if (teOptionChainChartInstance) teOptionChainChartInstance.destroy();

    const strikes = data.strikes.map(s => s.strike_price);
    const ceOi = data.strikes.map(s => s.ce_oi);
    const peOi = data.strikes.map(s => s.pe_oi);

    teOptionChainChartInstance = new Chart(ctxOi, {
      type: "bar",
      data: {
        labels: strikes,
        datasets: [
          {
            label: "Call OI (Resistance)",
            data: ceOi,
            backgroundColor: "rgba(0, 242, 254, 0.7)",
            borderColor: "var(--accent-cyan)",
            borderWidth: 1
          },
          {
            label: "Put OI (Support)",
            data: peOi,
            backgroundColor: "rgba(255, 77, 79, 0.7)",
            borderColor: "var(--accent-red)",
            borderWidth: 1
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#8b949e", font: { size: 10 } } },
          y: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#8b949e", font: { size: 10 } } }
        },
        plugins: {
          legend: { labels: { color: "#c9d1d9", font: { size: 11 } } },
          tooltip: {
            backgroundColor: "rgba(10, 16, 28, 0.95)",
            callbacks: {
              label: (c) => `${c.dataset.label}: ${Number(c.parsed.y).toLocaleString()} OI`
            }
          }
        }
      }
    });
  }

  // 2. PCR Timeline Chart
  const ctxPcr = document.getElementById("tePcrTimelineChart");
  if (ctxPcr && data.pcr_timeline) {
    if (tePcrChartInstance) tePcrChartInstance.destroy();

    const labels = data.pcr_timeline.map(p => p.time);
    const pcrs = data.pcr_timeline.map(p => p.pcr);
    const spots = data.pcr_timeline.map(p => p.spot);

    tePcrChartInstance = new Chart(ctxPcr, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "PCR (Put-Call Ratio)",
            data: pcrs,
            borderColor: "var(--accent-gold)",
            backgroundColor: "rgba(250, 204, 21, 0.1)",
            fill: true,
            tension: 0.2,
            borderWidth: 2,
            yAxisID: "yPcr"
          },
          {
            label: "Underlying Spot",
            data: spots,
            borderColor: "var(--accent-cyan)",
            borderWidth: 1.5,
            borderDash: [4, 4],
            pointRadius: 0,
            yAxisID: "ySpot"
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#8b949e", font: { size: 10 } } },
          yPcr: {
            position: "left",
            grid: { color: "rgba(255,255,255,0.05)" },
            ticks: { color: "var(--accent-gold)", font: { size: 10 } }
          },
          ySpot: {
            position: "right",
            grid: { drawOnChartArea: false },
            ticks: { color: "var(--accent-cyan)", font: { size: 10 } }
          }
        },
        plugins: {
          legend: { labels: { color: "#c9d1d9", font: { size: 11 } } }
        }
      }
    });
  }
}

// ── 8. Forensic Market Tape Replay ───────────────────────────────────────────
async function loadReplaySession() {
  const select = document.getElementById("teDateSelect");
  const dateStr = select ? select.value : "2026_09_11";
  const symInput = document.getElementById("replaySymbolInput");
  const sym = symInput ? symInput.value.toUpperCase() : "NIFTY";

  try {
    const res = await fetch(`/api/trading_engine/replay_data?date=${encodeURIComponent(dateStr)}&symbol=${encodeURIComponent(sym)}`);
    const json = await res.json();
    if (json.status !== "ok") return;

    currentReplaySession = json.data;
    currentReplayFrameIndex = 0;

    const scrubber = document.getElementById("replayScrubber");
    if (scrubber && currentReplaySession.frames) {
      scrubber.max = Math.max(0, currentReplaySession.frames.length - 1);
      scrubber.value = 0;
    }

    renderReplayFrame(0);
  } catch (err) {
    console.error("Error loading replay session:", err);
  }
}

function renderReplayFrame(frameIdx) {
  if (!currentReplaySession || !currentReplaySession.frames || currentReplaySession.frames.length === 0) return;
  const frames = currentReplaySession.frames;
  const idx = Math.max(0, Math.min(frames.length - 1, frameIdx));
  currentReplayFrameIndex = idx;
  const f = frames[idx];

  // Update Scrubber & Time Readout
  const scrubber = document.getElementById("replayScrubber");
  if (scrubber) scrubber.value = idx;
  const readout = document.getElementById("replayTimeReadout");
  if (readout) readout.innerText = f.time || "--";

  // Update KPI Cards
  const kpiPrice = document.getElementById("replayKpiPrice");
  if (kpiPrice) kpiPrice.innerText = `₹${f.close.toLocaleString()}`;
  const kpiTime = document.getElementById("replayKpiTime");
  if (kpiTime) kpiTime.innerText = `Bar: ${idx + 1} / ${frames.length} (${f.time})`;
  const kpiPnl = document.getElementById("replayKpiPnl");
  if (kpiPnl) {
    kpiPnl.innerText = `₹${f.cumulative_pnl.toLocaleString()}`;
    kpiPnl.style.color = f.cumulative_pnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';
  }
  const kpiInd = document.getElementById("replayKpiIndicators");
  if (kpiInd) {
    const isBull = f.supertrend_dir === 1;
    kpiInd.innerText = isBull ? "ST: Bullish ▲" : "ST: Bearish ▼";
    kpiInd.style.color = isBull ? 'var(--accent-green)' : 'var(--accent-red)';
  }

  // Draw Replay Chart: Window of past 40 bars up to idx
  const startIdx = Math.max(0, idx - 40);
  const windowFrames = frames.slice(startIdx, idx + 1);

  const ctx = document.getElementById("teReplayChart");
  if (ctx) {
    if (teReplayChartInstance) teReplayChartInstance.destroy();

    const labels = windowFrames.map(w => w.time);
    const closes = windowFrames.map(w => w.close);
    const supertrend = windowFrames.map(w => w.supertrend);
    const vwap = windowFrames.map(w => w.vwap);

    const datasets = [
      {
        label: "Price",
        data: closes,
        borderColor: "rgba(255, 255, 255, 0.9)",
        backgroundColor: "rgba(255, 255, 255, 0.05)",
        fill: true,
        borderWidth: 2,
        pointRadius: 2,
        pointHoverRadius: 5
      }
    ];

    const chkSt = document.getElementById("chkReplaySt");
    if (chkSt && chkSt.checked) {
      datasets.push({
        label: "Supertrend",
        data: supertrend,
        borderColor: "var(--accent-cyan)",
        borderWidth: 1.5,
        pointRadius: 0
      });
    }

    const chkVwap = document.getElementById("chkReplayVwap");
    if (chkVwap && chkVwap.checked) {
      datasets.push({
        label: "VWAP",
        data: vwap,
        borderColor: "var(--accent-gold)",
        borderDash: [3, 3],
        borderWidth: 1.5,
        pointRadius: 0
      });
    }

    teReplayChartInstance = new Chart(ctx, {
      type: "line",
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        scales: {
          x: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#8b949e", font: { size: 10 } } },
          y: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#8b949e", font: { size: 10 } } }
        },
        plugins: {
          legend: { labels: { color: "#c9d1d9", font: { size: 10 } } }
        }
      }
    });
  }

  // Populate Events Stream
  const eventsCount = document.getElementById("replayKpiEventsCount");
  const pastEvents = [];
  for (let i = 0; i <= idx; i++) {
    if (frames[i].events && frames[i].events.length > 0) {
      pastEvents.push(...frames[i].events);
    }
  }
  if (eventsCount) eventsCount.innerText = pastEvents.length;

  const tbody = document.getElementById("replayEventsBody");
  if (tbody) {
    if (pastEvents.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No events triggered up to ${f.time}.</td></tr>`;
    } else {
      tbody.innerHTML = pastEvents.slice(-12).reverse().map(ev => {
        const isAi = ev.type === "AI_EVALUATION";
        const actionCol = (ev.action === "BUY" || ev.action === "APPROVE") ? 'var(--accent-green)' : 'var(--accent-red)';
        return `
          <tr>
            <td style="color: var(--text-muted); font-weight: 600;">${ev.time || f.time}</td>
            <td><span class="card-badge" style="background: ${isAi ? 'rgba(0,242,254,0.15)' : 'rgba(250,204,21,0.15)'}; color: ${isAi ? 'var(--accent-cyan)' : 'var(--accent-gold)'};">${ev.type}</span></td>
            <td style="color: ${actionCol}; font-weight: 700;">${ev.action || ev.side || '--'}</td>
            <td>${ev.confidence ? `${Math.round(ev.confidence * 100)}%` : '--'}</td>
            <td style="font-size: 0.8rem; color: #c9d1d9; max-width: 320px;">${ev.reasoning || ev.title || '--'}</td>
            <td style="font-weight: 700; color: ${(ev.pnl || 0) >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'};">${ev.pnl !== undefined ? `₹${ev.pnl}` : '--'}</td>
          </tr>
        `;
      }).join("");
    }
  }
}

function toggleReplayPlay() {
  const btn = document.getElementById("btnReplayPlay");
  if (replayIsPlaying) {
    clearInterval(replayIntervalTimer);
    replayIsPlaying = false;
    if (btn) btn.innerText = "▶ Play";
  } else {
    if (!currentReplaySession) {
      loadReplaySession();
      return;
    }
    const speedSelect = document.getElementById("replaySpeedSelect");
    const speed = speedSelect ? parseInt(speedSelect.value) : 5;
    const intervalMs = Math.max(50, 1000 / speed);

    replayIntervalTimer = setInterval(() => {
      if (currentReplayFrameIndex < currentReplaySession.frames.length - 1) {
        renderReplayFrame(currentReplayFrameIndex + 1);
      } else {
        clearInterval(replayIntervalTimer);
        replayIsPlaying = false;
        if (btn) btn.innerText = "▶ Play";
      }
    }, intervalMs);

    replayIsPlaying = true;
    if (btn) btn.innerText = "⏸ Pause";
  }
}

function stepReplay(delta) {
  if (!currentReplaySession) return;
  renderReplayFrame(currentReplayFrameIndex + delta);
}

function seekReplay(idx) {
  if (!currentReplaySession) return;
  renderReplayFrame(idx);
}

function resetReplay() {
  if (replayIsPlaying) toggleReplayPlay();
  renderReplayFrame(0);
}

// ── 9. Robustness & Overfitting Defense ───────────────────────────────────────
async function fetchRobustnessAudit() {
  const select = document.getElementById("teDateSelect");
  const dateStr = select ? select.value : "2026_09_11";
  const stratSelect = document.getElementById("robStrategySelect");
  const strat = stratSelect ? stratSelect.value : "trading-engine-v4";
  const trialsInput = document.getElementById("robTrialsInput");
  const numTrials = trialsInput ? parseInt(trialsInput.value) : 25;

  try {
    const res = await fetch("/api/trading_engine/robustness_audit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date: dateStr, strategy: strat, num_trials: numTrials })
    });
    const json = await res.json();
    if (json.status !== "ok") return;

    const d = json.data;
    const m = d.statistical_metrics;
    const surf = d.parameter_surface;

    // Update KPIs
    const kpiDsr = document.getElementById("robKpiDsr");
    if (kpiDsr) kpiDsr.innerText = `${m.dsr}%`;
    const kpiPsr = document.getElementById("robKpiPsr");
    if (kpiPsr) kpiPsr.innerText = `${m.psr}%`;
    const kpiGrade = document.getElementById("robKpiGrade");
    if (kpiGrade) {
      kpiGrade.innerText = m.grade.split(" ")[0];
      kpiGrade.style.color = m.dsr >= 85 ? 'var(--accent-green)' : (m.dsr >= 70 ? 'var(--accent-cyan)' : 'var(--accent-red)');
    }
    const kpiHaircut = document.getElementById("robKpiHaircut");
    if (kpiHaircut) kpiHaircut.innerText = `-${m.haircut_pct}%`;
    const kpiPlateau = document.getElementById("robKpiPlateau");
    if (kpiPlateau) kpiPlateau.innerText = `${surf.plateau_score} / 100`;
    const kpiCliff = document.getElementById("robKpiCliffRisk");
    if (kpiCliff) kpiCliff.innerText = surf.cliff_risk;

    // Render Heatmap Matrix
    renderRobustnessGrid(surf);
  } catch (err) {
    console.error("Error fetching robustness audit:", err);
  }
}

function renderRobustnessGrid(surf) {
  const container = document.getElementById("robGridContainer");
  if (!container || !surf.grid) return;

  const xVals = surf.x_values;
  const yVals = surf.y_values;

  let html = `
    <table style="width: 100%; text-align: center; border-collapse: collapse; font-size: 0.82rem;">
      <thead>
        <tr>
          <th style="padding: 8px; color: var(--text-muted);">${surf.param_y} \\ ${surf.param_x}</th>
          ${xVals.map(x => `<th style="padding: 8px; color: var(--accent-cyan);">${x}</th>`).join("")}
        </tr>
      </thead>
      <tbody>
  `;

  yVals.forEach(y => {
    html += `<tr><td style="font-weight: 700; color: var(--accent-gold); padding: 8px;">${y}</td>`;
    xVals.forEach(x => {
      const node = surf.grid.find(g => Math.abs(g.x - x) < 0.01 && Math.abs(g.y - y) < 0.01);
      if (node) {
        const isCur = node.is_current;
        const color = node.sharpe >= 2.0 ? 'rgba(0, 245, 160, 0.3)' : (node.sharpe >= 1.2 ? 'rgba(0, 242, 254, 0.2)' : 'rgba(255, 77, 79, 0.2)');
        const border = isCur ? '2px solid var(--accent-cyan)' : '1px solid rgba(255,255,255,0.06)';
        html += `
          <td style="background: ${color}; border: ${border}; padding: 10px; border-radius: 4px;">
            <div style="font-weight: 800; color: #fff;">${node.sharpe} SR</div>
            <div style="font-size: 0.72rem; color: #c9d1d9;">${node.win_rate}% Win</div>
            ${isCur ? '<span style="font-size: 0.65rem; color: var(--accent-cyan); font-weight: bold;">[ACTIVE]</span>' : ''}
          </td>
        `;
      } else {
        html += `<td>--</td>`;
      }
    });
    html += `</tr>`;
  });

  html += `</tbody></table>`;
  container.innerHTML = html;
}

// ── 10. Multi-Strategy Portfolio Allocation ──────────────────────────────────
async function fetchPortfolioOptimization(method = "risk_parity") {
  try {
    const res = await fetch("/api/trading_engine/portfolio_optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ method, days: 30, initial_capital: 500000.0 })
    });
    const json = await res.json();
    if (json.status !== "ok") return;

    const d = json.data;
    const m = d.portfolio_metrics;

    // Update KPIs
    const kpiRet = document.getElementById("portKpiReturn");
    if (kpiRet) kpiRet.innerText = `+${m.annual_return_pct}%`;
    const kpiVol = document.getElementById("portKpiVol");
    if (kpiVol) kpiVol.innerText = `${m.annual_volatility_pct}%`;
    const kpiSharpe = document.getElementById("portKpiSharpe");
    if (kpiSharpe) kpiSharpe.innerText = `${m.sharpe_ratio}`;
    const kpiDiv = document.getElementById("portKpiDiv");
    if (kpiDiv) kpiDiv.innerText = `${m.diversification_ratio}x`;

    // Render Correlation Matrix
    const corrBody = document.getElementById("portCorrBody");
    if (corrBody && d.correlation_matrix) {
      corrBody.innerHTML = d.correlation_matrix.map(row => `
        <tr>
          <td style="font-weight: 700; color: #fff;">${row.strategy}</td>
          <td style="color: ${row.strat_v4 > 0.3 ? 'var(--accent-red)' : 'var(--accent-cyan)'};">${row.strat_v4}</td>
          <td style="color: ${row.strat_straddle > 0.3 ? 'var(--accent-red)' : 'var(--accent-cyan)'};">${row.strat_straddle}</td>
          <td style="color: ${row.strat_iron_condor > 0.3 ? 'var(--accent-red)' : 'var(--accent-cyan)'};">${row.strat_iron_condor}</td>
          <td style="color: ${row.strat_camarilla > 0.3 ? 'var(--accent-red)' : 'var(--accent-cyan)'};">${row.strat_camarilla}</td>
        </tr>
      `).join("");
    }

    // Render Blended Equity Chart
    renderPortfolioChart(d.equity_timeline, d.strategies);
  } catch (err) {
    console.error("Error optimizing portfolio:", err);
  }
}

function renderPortfolioChart(timeline, strategies) {
  const ctx = document.getElementById("tePortfolioChart");
  if (!ctx || !timeline) return;

  if (tePortfolioChartInstance) tePortfolioChartInstance.destroy();

  const labels = timeline.map(t => t.date);
  const blended = timeline.map(t => t.blended_equity);

  const colors = ["#00f2fe", "#00f5a0", "#facc15", "#a78bfa"];
  const datasets = [
    {
      label: "Blended Optimized Portfolio (₹)",
      data: blended,
      borderColor: "#ffffff",
      backgroundColor: "rgba(255, 255, 255, 0.1)",
      borderWidth: 3,
      fill: true,
      tension: 0.2
    }
  ];

  strategies.forEach((s, idx) => {
    datasets.push({
      label: `${s.name} (${s.weight_pct}%)`,
      data: timeline.map(t => t[s.id]),
      borderColor: colors[idx % colors.length],
      borderWidth: 1.5,
      borderDash: [3, 3],
      pointRadius: 0,
      tension: 0.2
    });
  });

  tePortfolioChartInstance = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#8b949e", font: { size: 10 } } },
        y: {
          grid: { color: "rgba(255,255,255,0.05)" },
          ticks: { color: "#8b949e", font: { size: 10 }, callback: v => `₹${Number(v).toLocaleString()}` }
        }
      },
      plugins: {
        legend: { labels: { color: "#c9d1d9", font: { size: 10 } } }
      }
    }
  });
}

// ── 11. Adaptive Regime Auto-Tuner ───────────────────────────────────────────
async function fetchAutoTune() {
  const select = document.getElementById("teDateSelect");
  const dateStr = select ? select.value : "2026_09_11";

  try {
    const res = await fetch("/api/trading_engine/auto_tune", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date: dateStr, apply: false })
    });
    const json = await res.json();
    if (json.status !== "ok") return;

    const d = json.data;
    const r = d.regime;
    const m = d.market_indicators;

    // Update Regime Card
    const nameEl = document.getElementById("atRegimeName");
    if (nameEl) nameEl.innerText = r.name;
    const badgeEl = document.getElementById("atRegimeBadge");
    if (badgeEl) {
      badgeEl.innerText = r.code;
      badgeEl.style.color = r.badge_color;
    }
    const descEl = document.getElementById("atRegimeDesc");
    if (descEl) descEl.innerText = r.description;

    // Update Market KPIs
    const kpiMove = document.getElementById("atKpiMove");
    if (kpiMove) kpiMove.innerText = `${m.nifty_change_pct > 0 ? '+' : ''}${m.nifty_change_pct}%`;
    const kpiRange = document.getElementById("atKpiRange");
    if (kpiRange) kpiRange.innerText = `${m.nifty_range_pct}%`;
    const kpiVix = document.getElementById("atKpiVix");
    if (kpiVix) kpiVix.innerText = `${m.vix_level}`;
    const kpiEff = document.getElementById("atKpiEff");
    if (kpiEff) kpiEff.innerText = `${m.execution_efficiency}%`;
    const kpiPrec = document.getElementById("atKpiPrec");
    if (kpiPrec) kpiPrec.innerText = `${m.ai_precision}%`;

    // Populate Recommendations Table
    const tbody = document.getElementById("atRecsBody");
    if (tbody && d.recommendations) {
      tbody.innerHTML = d.recommendations.map(rec => `
        <tr>
          <td style="font-family: monospace; font-weight: 700; color: var(--accent-cyan);">${rec.key}</td>
          <td style="font-family: monospace; color: var(--text-muted);">${rec.current}</td>
          <td style="font-family: monospace; font-weight: 800; color: var(--accent-green);">${rec.recommended}</td>
          <td style="font-size: 0.82rem; color: #c9d1d9;">${rec.rationale}</td>
        </tr>
      `).join("");
    }
  } catch (err) {
    console.error("Error fetching auto-tune diagnosis:", err);
  }
}

async function applyAutoTune() {
  const btn = document.getElementById("btnApplyAutoTune");
  const banner = document.getElementById("atSyncBanner");
  const select = document.getElementById("teDateSelect");
  const dateStr = select ? select.value : "2026_09_11";

  if (btn) {
    btn.disabled = true;
    btn.innerText = "Applying Updates...";
  }

  try {
    const res = await fetch("/api/trading_engine/auto_tune", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date: dateStr, apply: true })
    });
    const json = await res.json();
    if (json.status === "ok" && json.sync_result) {
      if (banner) {
        banner.style.display = "block";
        banner.innerHTML = `
          <strong>✓ Tuned Parameters Successfully Synced to Production (.env):</strong><br>
          Updated Keys: <code>${Object.keys(json.sync_result.updated_keys || {}).join(", ")}</code><br>
          <span style="font-size: 0.75rem; color: #8b949e;">Safety Backup: ${json.sync_result.backup_file || 'created'}</span>
        `;
      }
    }
  } catch (err) {
    console.error("Error applying auto-tune updates:", err);
    if (banner) {
      banner.style.display = "block";
      banner.style.background = "rgba(255,77,79,0.15)";
      banner.style.borderColor = "var(--accent-red)";
      banner.innerHTML = `Failed to apply tuning updates: ${err.message}`;
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = "⚡ Apply Tuned Parameters to Trading Engine (.env)";
    }
  }
}




// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initTradingEngineInsights);
} else {
  initTradingEngineInsights();
}
